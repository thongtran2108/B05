# -*- coding: utf-8 -*-
"""Panel cho 1 bên (Trái / Phải). Mỗi panel có 1 SideWorker + 1 tay scan riêng.

Bố cục dạng "card": chọn mã liệu/loại đầu → card SN → tiến độ → card kết quả
→ nút điều khiển → khu giả lập → BẢNG DỮ LIỆU (SN ↔ giá trị) + NHẬT KÝ.

Sự kiện từ worker (luồng nền) được đưa về luồng GUI an toàn qua signal Qt.
"""

from PySide6.QtCore import Qt, QObject, Signal, Slot
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFrame, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPlainTextEdit, QProgressBar, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..config import head_count
from ..core.side_worker import ST_IDLE, ST_WAIT_SCAN, ST_RUNNING, SideWorker
from ..hardware.plc_client import make_plc_client
from ..hardware.scanner import SerialScanner
from .theme import GREEN, RED, AMBER, ELEV2, BORDER2, CAPTION

TABLE_COLS = ["SN", "Loại", "Đầu", "Judge", "Thời gian", "MES", "Giá trị (Data01..N)"]
MAX_TABLE_ROWS = 1000


class _EventBridge(QObject):
    """Cầu nối: phát sự kiện worker (luồng nền) -> slot ở luồng GUI."""
    event = Signal(str, dict)


class SidePanel(QGroupBox):
    def __init__(self, side_key, cfg, parent=None):
        title = "BÊN TRÁI · CCD1" if side_key == "left" else "BÊN PHẢI · CCD2"
        super().__init__(title, parent)
        self.side_key = side_key
        self.cfg = cfg
        self.worker = None
        self.scanner = None
        self._pending_mes = []          # các ô cột MES của SN đang chạy

        self._bold = QFont(); self._bold.setBold(True)
        self._bridge = _EventBridge()
        self._bridge.event.connect(self._on_event)

        self._build_ui()
        self._reload_materials()

    # ------------------------------------------------------------------ #
    #  Dựng widget                                                        #
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 18, 12, 12)
        root.setSpacing(9)

        # --- Chọn mã liệu + loại đầu ---
        sel = QHBoxLayout()
        sel.addWidget(QLabel("Mã liệu:"))
        self.cbo_material = QComboBox()
        self.cbo_material.setMinimumWidth(130)
        sel.addWidget(self.cbo_material, 1)
        sel.addSpacing(10)
        sel.addWidget(QLabel("Loại đầu:"))
        self.cbo_type = QComboBox()
        self.cbo_type.addItems(["8X", "16X"])
        self.cbo_type.setFixedWidth(84)
        sel.addWidget(self.cbo_type)
        root.addLayout(sel)
        self.cbo_material.currentIndexChanged.connect(self._selection_changed)
        self.cbo_type.currentIndexChanged.connect(self._selection_changed)

        # --- Trạng thái + đèn PLC ---
        srow = QHBoxLayout()
        self.lbl_plc = QLabel("● PLC: --")
        self.lbl_state = QLabel("Trạng thái: chưa bật")
        self.lbl_state.setObjectName("muted")
        srow.addWidget(self.lbl_plc)
        srow.addStretch(1)
        srow.addWidget(self.lbl_state)
        root.addLayout(srow)

        # --- Card SN ---
        sn_card = QFrame(); sn_card.setObjectName("snCard")
        sc = QVBoxLayout(sn_card)
        sc.setContentsMargins(12, 8, 12, 8); sc.setSpacing(1)
        cap = QLabel("SERIAL NUMBER"); cap.setObjectName("caption")
        cap.setAlignment(Qt.AlignCenter)
        self.lbl_sn = QLabel("——"); self.lbl_sn.setObjectName("snValue")
        self.lbl_sn.setAlignment(Qt.AlignCenter)
        sc.addWidget(cap); sc.addWidget(self.lbl_sn)
        root.addWidget(sn_card)

        # --- Tiến độ ---
        self.progress = QProgressBar()
        self.progress.setFormat("Đầu %v/%m")
        self.progress.setRange(0, 1); self.progress.setValue(0)
        root.addWidget(self.progress)

        # --- Card kết quả ---
        self.lbl_result = QLabel("——")
        self.lbl_result.setAlignment(Qt.AlignCenter)
        self.lbl_result.setMinimumHeight(64)
        fr = QFont(); fr.setPointSize(26); fr.setBold(True)
        self.lbl_result.setFont(fr)
        self._set_result_style(None)
        root.addWidget(self.lbl_result)

        # --- Nút Bắt đầu / Dừng ---
        brow = QHBoxLayout()
        self.btn_start = QPushButton("▶  Bắt đầu"); self.btn_start.setObjectName("startBtn")
        self.btn_stop = QPushButton("■  Dừng"); self.btn_stop.setObjectName("stopBtn")
        self.btn_stop.setEnabled(False)
        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop.clicked.connect(self._on_stop)
        brow.addWidget(self.btn_start); brow.addWidget(self.btn_stop)
        root.addLayout(brow)

        # --- Khu giả lập (chỉ hiện khi simulation) ---
        self.sim_box = QFrame()
        sbl = QHBoxLayout(self.sim_box)
        sbl.setContentsMargins(0, 0, 0, 0)
        self.txt_sn = QLineEdit(); self.txt_sn.setPlaceholderText("Nhập SN giả lập…")
        self.btn_scan = QPushButton("Quét (giả lập)"); self.btn_scan.setObjectName("ghostBtn")
        self.btn_trig = QPushButton("Tín hiệu PLC (giả lập)"); self.btn_trig.setObjectName("ghostBtn")
        self.btn_scan.clicked.connect(self._on_sim_scan)
        self.btn_trig.clicked.connect(self._on_sim_trigger)
        self.txt_sn.returnPressed.connect(self._on_sim_scan)
        sbl.addWidget(self.txt_sn, 1)
        sbl.addWidget(self.btn_scan)
        sbl.addWidget(self.btn_trig)
        root.addWidget(self.sim_box)
        self.sim_box.setVisible(self.cfg.simulation)

        # --- Splitter: BẢNG DỮ LIỆU (trên) + NHẬT KÝ (dưới) ---
        split = QSplitter(Qt.Vertical)

        tbox = QWidget(); tlay = QVBoxLayout(tbox)
        tlay.setContentsMargins(0, 0, 0, 0); tlay.setSpacing(4)
        thead = QHBoxLayout()
        tcap = QLabel("BẢNG DỮ LIỆU"); tcap.setObjectName("caption")
        self.btn_clear = QPushButton("Xóa bảng"); self.btn_clear.setObjectName("ghostBtn")
        self.btn_clear.setFixedWidth(96)
        self.btn_clear.clicked.connect(self._clear_table)
        thead.addWidget(tcap); thead.addStretch(1); thead.addWidget(self.btn_clear)
        tlay.addLayout(thead)
        self.table = self._build_table()
        tlay.addWidget(self.table)
        split.addWidget(tbox)

        lbox = QWidget(); llay = QVBoxLayout(lbox)
        llay.setContentsMargins(0, 0, 0, 0); llay.setSpacing(4)
        lcap = QLabel("NHẬT KÝ"); lcap.setObjectName("caption")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(800)
        llay.addWidget(lcap); llay.addWidget(self.log)
        split.addWidget(lbox)

        split.setStretchFactor(0, 3); split.setStretchFactor(1, 1)
        split.setSizes([340, 150])
        root.addWidget(split, 1)

    def _build_table(self):
        t = QTableWidget(0, len(TABLE_COLS))
        t.setHorizontalHeaderLabels(TABLE_COLS)
        t.verticalHeader().setVisible(False)
        t.setAlternatingRowColors(True)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        t.setWordWrap(False)
        hh = t.horizontalHeader()
        for i in range(len(TABLE_COLS) - 1):
            hh.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(len(TABLE_COLS) - 1, QHeaderView.Interactive)
        t.setColumnWidth(len(TABLE_COLS) - 1, 520)
        return t

    # ------------------------------------------------------------------ #
    #  Cấu hình / mã liệu                                                 #
    # ------------------------------------------------------------------ #
    def apply_config(self, cfg):
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
        self.worker = SideWorker(self.side_key, self.cfg, plc, self._emit_event)
        self.worker.start()
        self.worker.arm(material, head_type)

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
            self.scanner.stop(); self.scanner = None
        if self.worker:
            self.worker.disarm(); self.worker.stop(); self.worker = None

    # ------------------------------------------------------------------ #
    #  Lựa chọn / giả lập / bảng                                          #
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

    def _clear_table(self):
        self.table.setRowCount(0)
        self._pending_mes = []

    # ------------------------------------------------------------------ #
    #  Nhận sự kiện worker (đưa về luồng GUI)                             #
    # ------------------------------------------------------------------ #
    def _emit_event(self, etype, **data):
        self._bridge.event.emit(etype, data)

    @Slot(str, dict)
    def _on_event(self, etype, data):
        if etype == "log":
            self._append_log(data.get("text", ""))
        elif etype == "status":
            self.lbl_state.setText("Trạng thái: " + data.get("text", ""))
        elif etype == "sn":
            self.lbl_sn.setText(data.get("sn", "——"))
            self._set_result_style(None)
            self.lbl_result.setText("…")
            self._pending_mes = []        # bắt đầu nhóm hàng cho SN mới
        elif etype == "progress":
            done = data.get("done", 0); total = max(1, data.get("total", 1))
            self.progress.setRange(0, total)
            self.progress.setValue(done)
        elif etype == "reading":
            self._add_reading_row(data)
        elif etype == "error":
            self._show_error(data)
        elif etype == "result":
            self._show_result(data.get("result", ""), data.get("ok", False))
            self._mark_uploaded(data.get("result", ""), data.get("ok", False))
        elif etype == "plc":
            self._set_plc(data.get("connected", False))
        elif etype == "state":
            st = data.get("state", "")
            label = {ST_IDLE: "chưa bật", ST_WAIT_SCAN: "chờ quét mã",
                     ST_RUNNING: "đang chạy"}.get(st, st)
            self.lbl_state.setText("Trạng thái: " + label)

    # ------------------------------------------------------------------ #
    #  Bảng dữ liệu                                                       #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _fmt(v):
        if isinstance(v, float):
            s = "%.4f" % v
            if "." in s:
                s = s.rstrip("0").rstrip(".")
            return s
        return str(v)

    def _add_reading_row(self, d):
        t = self.table
        r = t.rowCount(); t.insertRow(r)
        vals = d.get("values", [])
        vals_str = ", ".join(self._fmt(v) for v in vals)
        judge = str(d.get("judge", "")).upper()
        texts = [
            str(d.get("sn", "")),
            str(d.get("head_type", "")),
            "%d/%d" % (d.get("index", 0), d.get("total", 0)),
            judge or "—",
            str(d.get("time", "")),
            "",                              # MES (điền khi upload xong)
            vals_str,
        ]
        for c, txt in enumerate(texts):
            it = QTableWidgetItem(txt)
            if c in (1, 2, 3, 5):
                it.setTextAlignment(Qt.AlignCenter)
            if c == 6:
                it.setToolTip("%d giá trị:\n%s" % (len(vals), vals_str))
            t.setItem(r, c, it)

        jitem = t.item(r, 3)
        jitem.setForeground(QColor(GREEN if judge == "OK" else RED))
        jitem.setFont(self._bold)
        if judge != "OK":
            for c in range(t.columnCount()):
                t.item(r, c).setBackground(QColor("#2a1e22"))

        self._pending_mes.append(t.item(r, 5))
        t.scrollToBottom()
        while t.rowCount() > MAX_TABLE_ROWS:
            t.removeRow(0)

    def _mark_uploaded(self, result, ok):
        for it in self._pending_mes:
            if it is None:
                continue
            it.setText("✔" if ok else "✗")
            it.setTextAlignment(Qt.AlignCenter)
            it.setForeground(QColor(GREEN if ok else AMBER))
            it.setToolTip("Đã gửi MES (result=%s)" % result if ok
                          else "Gửi MES lỗi — xem nhật ký")
        self._pending_mes = []

    def _show_error(self, d):
        """Hiển thị lỗi thiếu dữ liệu: banner đỏ + 1 dòng LỖI trong bảng."""
        msg = str(d.get("message", "")).replace("\n", " ")
        self.lbl_result.setText("LỖI DỮ LIỆU")
        self.lbl_result.setStyleSheet(
            "background:#a3282d; color:#ffecec; border-radius:10px; font-weight:800;")
        self.lbl_state.setText("Trạng thái: LỖI — " + msg)

        t = self.table
        r = t.rowCount(); t.insertRow(r)
        texts = [str(d.get("sn", "")), str(d.get("head_type", "")),
                 "%d/%d" % (d.get("index", 0), d.get("total", 0)),
                 "LỖI", "—", "—", msg]
        for c, txt in enumerate(texts):
            it = QTableWidgetItem(txt)
            if c in (1, 2, 3, 5):
                it.setTextAlignment(Qt.AlignCenter)
            if c == 6:
                it.setToolTip(msg)
            it.setBackground(QColor("#2a1e22"))
            t.setItem(r, c, it)
        jitem = t.item(r, 3)
        jitem.setForeground(QColor(RED)); jitem.setFont(self._bold)
        t.scrollToBottom()
        self._pending_mes = []          # SN bị hủy, không có gì để đánh dấu MES

    # ------------------------------------------------------------------ #
    #  Helper hiển thị                                                    #
    # ------------------------------------------------------------------ #
    def _append_log(self, text):
        if text:
            self.log.appendPlainText(text)

    def _set_plc(self, connected):
        if connected:
            self.lbl_plc.setText("● PLC: kết nối")
            self.lbl_plc.setStyleSheet("color: %s; font-weight:600;" % GREEN)
        else:
            self.lbl_plc.setText("● PLC: mất kết nối")
            self.lbl_plc.setStyleSheet("color: %s; font-weight:600;" % RED)

    def _set_result_style(self, ok):
        base = "border-radius:10px; font-weight:800;"
        if ok is None:
            self.lbl_result.setStyleSheet(
                "background:%s; color:%s; border:1px solid %s; %s"
                % (ELEV2, CAPTION, BORDER2, base))
        elif ok:
            self.lbl_result.setStyleSheet(
                "background:#1f7a4d; color:#eafff4; %s" % base)
        else:
            self.lbl_result.setStyleSheet(
                "background:#a3282d; color:#ffecec; %s" % base)

    def _show_result(self, result, ok):
        res = str(result).upper()
        if not ok:                            # gửi MES lỗi -> viền hổ phách
            self.lbl_result.setText(res + " (gửi lỗi)")
            self.lbl_result.setStyleSheet(
                "background:#9c6b1f; color:#fff; border-radius:10px; font-weight:800;")
        else:
            self.lbl_result.setText("OK" if res == "OK" else "NG")
            self._set_result_style(res == "OK")
