# -*- coding: utf-8 -*-
"""Hộp thoại Setting: chỉnh toàn bộ cấu hình và quản lý mã liệu.

Gồm các tab:
  - Chung   : chế độ giả lập, chu kỳ poll, đường dẫn thư mục dữ liệu
  - PLC     : IP / Port / timeout của PLC chung
  - API MES : URL, timeout, số lần retry, định dạng trường data
  - Bên trái / Bên phải : cổng COM tay scan, tiền tố CCD, địa chỉ bit handshake
  - Mã liệu : bảng thêm/sửa/xóa mã liệu (tên + số đầu 8X + số đầu 16X),
              kèm nút nhập hàng loạt từ file Excel/CSV
"""

import copy

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from ..config import AppConfig, MaterialConfig
from ..material_import import parse_materials


def _section(title):
    """Nhãn tiêu đề nhóm trong form Setting."""
    lbl = QLabel(title)
    lbl.setStyleSheet("color:#9fb4d8; font-weight:700; margin-top:6px;")
    return lbl


class SettingsDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Setting")
        self.resize(560, 520)
        self.cfg = copy.deepcopy(cfg)     # làm việc trên bản sao

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.tabs.addTab(self._tab_general(), "Chung")
        self.tabs.addTab(self._tab_plc(), "PLC")
        self.tabs.addTab(self._tab_api(), "API MES")
        self.tabs.addTab(self._tab_side("left"), "Bên trái")
        self.tabs.addTab(self._tab_side("right"), "Bên phải")
        self.tabs.addTab(self._tab_materials(), "Mã liệu")

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ------------------------------------------------------------------ #
    #  Tab Chung                                                          #
    # ------------------------------------------------------------------ #
    def _tab_general(self):
        w = QWidget(); form = QFormLayout(w)
        self.chk_sim = QCheckBox("Chế độ giả lập (không cần PLC / tay scan)")
        self.chk_sim.setChecked(self.cfg.simulation)
        form.addRow(self.chk_sim)

        self.spn_poll = QSpinBox(); self.spn_poll.setRange(20, 5000)
        self.spn_poll.setValue(self.cfg.poll_interval_ms)
        self.spn_poll.setSuffix(" ms")
        form.addRow("Chu kỳ đọc PLC:", self.spn_poll)

        self.spn_hs = QDoubleSpinBox(); self.spn_hs.setRange(0.5, 120)
        self.spn_hs.setValue(self.cfg.handshake_timeout_s)
        self.spn_hs.setSuffix(" s")
        form.addRow("Timeout chờ PLC nhả trigger:", self.spn_hs)

        # đường dẫn
        self.txt_base = QLineEdit(self.cfg.paths.base_dir)
        browse = QPushButton("Chọn…")
        browse.clicked.connect(self._browse_base)
        h = QHBoxLayout(); h.addWidget(self.txt_base, 1); h.addWidget(browse)
        hb = QWidget(); hb.setLayout(h)
        form.addRow("Thư mục gốc dữ liệu:", hb)

        self.txt_sub8 = QLineEdit(self.cfg.paths.sub_8x)
        self.txt_sub16 = QLineEdit(self.cfg.paths.sub_16x)
        self.txt_lglob = QLineEdit(self.cfg.paths.left_glob)
        self.txt_rglob = QLineEdit(self.cfg.paths.right_glob)
        form.addRow("Thư mục con 8X:", self.txt_sub8)
        form.addRow("Thư mục con 16X:", self.txt_sub16)
        form.addRow("Mẫu tên file Trái:", self.txt_lglob)
        form.addRow("Mẫu tên file Phải:", self.txt_rglob)
        form.addRow(QLabel("Đường dẫn = <gốc>/<con 8X|16X>/<YYYYMMDD>/CCD1*|CCD2*"))

        self.chk_today = QCheckBox(
            "Chỉ lấy dữ liệu của NGÀY HÔM NAY (báo lỗi nếu thiếu thư mục/file)")
        self.chk_today.setChecked(self.cfg.paths.require_today)
        form.addRow(self.chk_today)
        return w

    def _browse_base(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục gốc dữ liệu",
                                             self.txt_base.text())
        if d:
            self.txt_base.setText(d)

    # ------------------------------------------------------------------ #
    #  Tab PLC                                                            #
    # ------------------------------------------------------------------ #
    def _tab_plc(self):
        w = QWidget(); form = QFormLayout(w)
        self.txt_plc_ip = QLineEdit(self.cfg.plc.ip)
        self.spn_plc_port = QSpinBox(); self.spn_plc_port.setRange(1, 65535)
        self.spn_plc_port.setValue(self.cfg.plc.port)
        self.spn_plc_to = QDoubleSpinBox(); self.spn_plc_to.setRange(0.2, 30)
        self.spn_plc_to.setValue(self.cfg.plc.timeout); self.spn_plc_to.setSuffix(" s")
        form.addRow("IP PLC chung:", self.txt_plc_ip)
        form.addRow("Port:", self.spn_plc_port)
        form.addRow("Timeout:", self.spn_plc_to)
        form.addRow(QLabel("Mỗi bên có thể đặt IP/Port riêng trong tab Bên trái/phải."))
        return w

    # ------------------------------------------------------------------ #
    #  Tab API                                                            #
    # ------------------------------------------------------------------ #
    def _tab_api(self):
        w = QWidget(); form = QFormLayout(w)
        self.txt_url = QLineEdit(self.cfg.api.url)
        self.spn_api_to = QDoubleSpinBox(); self.spn_api_to.setRange(0.5, 60)
        self.spn_api_to.setValue(self.cfg.api.timeout); self.spn_api_to.setSuffix(" s")
        self.spn_retries = QSpinBox(); self.spn_retries.setRange(1, 10)
        self.spn_retries.setValue(self.cfg.api.retries)
        self.chk_verify = QCheckBox("Kiểm tra chứng chỉ SSL")
        self.chk_verify.setChecked(self.cfg.api.verify_ssl)
        self.cbo_fmt = QComboBox()
        self.cbo_fmt.addItems(["values_only", "full_row", "structured"])
        self.cbo_fmt.setCurrentText(self.cfg.api.data_format)
        self.chk_proxy = QCheckBox("Đi qua proxy hệ thống")
        self.chk_proxy.setChecked(self.cfg.api.use_proxy)
        self.txt_proxy = QLineEdit(self.cfg.api.proxy)
        self.txt_proxy.setPlaceholderText("vd http://10.0.0.1:8080 (để trống = proxy hệ thống)")

        # --- POST: upload kết quả ---
        form.addRow(_section("POST — Upload kết quả"))
        form.addRow("URL POST:", self.txt_url)
        form.addRow("Timeout:", self.spn_api_to)
        form.addRow("Số lần retry:", self.spn_retries)
        form.addRow(self.chk_verify)
        form.addRow("Định dạng trường data:", self.cbo_fmt)
        form.addRow(QLabel("values_only = chỉ Data01..N | full_row = cả dòng | "
                           "structured = key:value"))
        self.txt_post_ok = QLineEdit(self.cfg.api.post_ok_contains)
        self.txt_post_ok.setPlaceholderText("vd 200 (để trống = chỉ cần HTTP 2xx)")
        form.addRow("POST OK khi body chứa:", self.txt_post_ok)

        # --- GET: kiểm tra SN trước khi chạy ---
        form.addRow(_section("GET — Kiểm tra SN trước khi chạy"))
        self.chk_check = QCheckBox("Bật kiểm tra SN bằng GET")
        self.chk_check.setChecked(self.cfg.api.check_enabled)
        self.txt_check_pre = QLineEdit(self.cfg.api.check_url_prefix)
        self.txt_check_pre.setPlaceholderText("vd http://mes/api/check?sn=")
        self.txt_check_suf = QLineEdit(self.cfg.api.check_url_suffix)
        self.txt_check_suf.setPlaceholderText("vd &station=OP10 (có thể để trống)")
        self.txt_check_ok = QLineEdit(self.cfg.api.check_ok_contains)
        self.txt_check_ok.setPlaceholderText("vd 0 — body chứa chuỗi này thì SN hợp lệ")
        form.addRow(self.chk_check)
        form.addRow("URL GET (tiền tố):", self.txt_check_pre)
        form.addRow("URL GET (hậu tố):", self.txt_check_suf)
        form.addRow("SN hợp lệ khi body chứa:", self.txt_check_ok)
        form.addRow(QLabel("GET tới: <tiền tố> + SN + <hậu tố>. SN sai -> CHẶN, "
                           "chờ quét mã khác (không tải lên)."))

        # --- Proxy ---
        form.addRow(_section("Proxy"))
        form.addRow(self.chk_proxy)
        form.addRow("Proxy thủ công:", self.txt_proxy)
        form.addRow(QLabel("MES nội bộ: BỎ chọn proxy. Chỉ tích nếu MES nằm ngoài "
                           "mạng và phải qua proxy công ty."))
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(w)
        return scroll

    # ------------------------------------------------------------------ #
    #  Tab Bên trái / phải                                                #
    # ------------------------------------------------------------------ #
    def _tab_side(self, key):
        side = getattr(self.cfg, key)
        w = QWidget(); form = QFormLayout(w)
        port = QLineEdit(side.scanner_port)
        baud = QSpinBox(); baud.setRange(1200, 921600); baud.setValue(side.scanner_baud)
        ccd = QComboBox(); ccd.addItems(["CCD1", "CCD2"])
        ccd.setCurrentText(side.ccd_prefix)
        t8 = QLineEdit(side.trig_8x); d8 = QLineEdit(side.done_8x)
        t16 = QLineEdit(side.trig_16x); d16 = QLineEdit(side.done_16x)
        pip = QLineEdit(side.plc_ip)
        pport = QSpinBox(); pport.setRange(0, 65535); pport.setValue(side.plc_port)

        form.addRow("Cổng COM tay scan:", port)
        form.addRow("Baudrate:", baud)
        form.addRow("Tiền tố file (CCD):", ccd)
        form.addRow("Bit trigger 8X:", t8)
        form.addRow("Bit done 8X:", d8)
        form.addRow("Bit trigger 16X:", t16)
        form.addRow("Bit done 16X:", d16)
        form.addRow("PLC IP riêng (trống = chung):", pip)
        form.addRow("PLC Port riêng (0 = chung):", pport)

        # lưu tham chiếu widget để đọc lại khi accept
        setattr(self, "_w_%s" % key, {
            "scanner_port": port, "scanner_baud": baud, "ccd_prefix": ccd,
            "trig_8x": t8, "done_8x": d8, "trig_16x": t16, "done_16x": d16,
            "plc_ip": pip, "plc_port": pport,
        })
        return w

    # ------------------------------------------------------------------ #
    #  Tab Mã liệu                                                        #
    # ------------------------------------------------------------------ #
    def _tab_materials(self):
        w = QWidget(); v = QVBoxLayout(w)
        self.tbl = QTableWidget(0, 3)
        self.tbl.setHorizontalHeaderLabels(["Tên mã liệu", "Số đầu 8X", "Số đầu 16X"])
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        v.addWidget(self.tbl)
        for m in self.cfg.materials:
            self._add_material_row(m.name, m.heads_8x, m.heads_16x)

        h = QHBoxLayout()
        b_add = QPushButton("Thêm mã liệu")
        b_imp = QPushButton("Nhập từ Excel…")
        b_del = QPushButton("Xóa dòng chọn")
        b_add.clicked.connect(lambda: self._add_material_row("MÃ_MỚI", 0, 0))
        b_imp.clicked.connect(self._import_materials)
        b_del.clicked.connect(self._del_material_row)
        h.addWidget(b_add); h.addWidget(b_imp); h.addWidget(b_del); h.addStretch(1)
        v.addLayout(h)
        v.addWidget(QLabel(
            "Nhập từ Excel: file 3 cột (Tên mã liệu | Số đầu 8X | Số đầu 16X). "
            "Trùng tên sẽ được cập nhật, mã mới sẽ thêm vào."))
        return w

    def _add_material_row(self, name, h8, h16):
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)
        self.tbl.setItem(r, 0, QTableWidgetItem(str(name)))
        self.tbl.setItem(r, 1, QTableWidgetItem(str(h8)))
        self.tbl.setItem(r, 2, QTableWidgetItem(str(h16)))

    def _del_material_row(self):
        r = self.tbl.currentRow()
        if r >= 0:
            self.tbl.removeRow(r)

    def _material_rows_by_name(self):
        """Map {tên mã liệu -> chỉ số dòng} của các mã hiện có trong bảng."""
        out = {}
        for r in range(self.tbl.rowCount()):
            it = self.tbl.item(r, 0)
            name = it.text().strip() if it else ""
            if name and name not in out:
                out[name] = r
        return out

    def _import_materials(self):
        """Chọn file Excel/CSV -> nạp mã liệu vào bảng (gộp theo tên)."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file mã liệu (Excel/CSV)", self.cfg.paths.base_dir,
            "Excel/CSV (*.xlsx *.xls *.xlsm *.csv);;Tất cả file (*)")
        if not path:
            return
        try:
            materials, skipped = parse_materials(path)
        except Exception as ex:               # noqa: BLE001
            QMessageBox.critical(self, "Nhập mã liệu",
                                 "Không đọc được file:\n%s" % ex)
            return
        if not materials:
            QMessageBox.warning(
                self, "Nhập mã liệu",
                "Không tìm thấy mã liệu hợp lệ trong file.\n"
                "Cần 3 cột: Tên mã liệu | Số đầu 8X | Số đầu 16X.")
            return

        existing = self._material_rows_by_name()
        added = updated = 0
        for m in materials:
            if m.name in existing:            # trùng tên -> cập nhật số đầu
                r = existing[m.name]
                self.tbl.setItem(r, 1, QTableWidgetItem(str(m.heads_8x)))
                self.tbl.setItem(r, 2, QTableWidgetItem(str(m.heads_16x)))
                updated += 1
            else:                             # mã mới -> thêm dòng
                self._add_material_row(m.name, m.heads_8x, m.heads_16x)
                existing[m.name] = self.tbl.rowCount() - 1
                added += 1

        msg = "Đã nhập từ:\n%s\n\nThêm mới: %d — Cập nhật: %d" % (
            path, added, updated)
        if skipped:
            msg += "\nBỏ qua %d dòng không có tên mã." % skipped
        QMessageBox.information(self, "Nhập mã liệu", msg)

    # ------------------------------------------------------------------ #
    #  Đọc widget -> cấu hình                                             #
    # ------------------------------------------------------------------ #
    def _collect(self):
        c = self.cfg
        c.simulation = self.chk_sim.isChecked()
        c.poll_interval_ms = self.spn_poll.value()
        c.handshake_timeout_s = self.spn_hs.value()

        c.paths.base_dir = self.txt_base.text().strip()
        c.paths.sub_8x = self.txt_sub8.text().strip()
        c.paths.sub_16x = self.txt_sub16.text().strip()
        c.paths.left_glob = self.txt_lglob.text().strip() or "CCD1*"
        c.paths.right_glob = self.txt_rglob.text().strip() or "CCD2*"
        c.paths.require_today = self.chk_today.isChecked()

        c.plc.ip = self.txt_plc_ip.text().strip()
        c.plc.port = self.spn_plc_port.value()
        c.plc.timeout = self.spn_plc_to.value()

        c.api.url = self.txt_url.text().strip()
        c.api.timeout = self.spn_api_to.value()
        c.api.retries = self.spn_retries.value()
        c.api.verify_ssl = self.chk_verify.isChecked()
        c.api.data_format = self.cbo_fmt.currentText()
        c.api.use_proxy = self.chk_proxy.isChecked()
        c.api.proxy = self.txt_proxy.text().strip()
        c.api.post_ok_contains = self.txt_post_ok.text().strip()
        c.api.check_enabled = self.chk_check.isChecked()
        c.api.check_url_prefix = self.txt_check_pre.text().strip()
        c.api.check_url_suffix = self.txt_check_suf.text().strip()
        c.api.check_ok_contains = self.txt_check_ok.text().strip()

        for key in ("left", "right"):
            ws = getattr(self, "_w_%s" % key)
            side = getattr(c, key)
            side.scanner_port = ws["scanner_port"].text().strip()
            side.scanner_baud = ws["scanner_baud"].value()
            side.ccd_prefix = ws["ccd_prefix"].currentText()
            side.trig_8x = ws["trig_8x"].text().strip()
            side.done_8x = ws["done_8x"].text().strip()
            side.trig_16x = ws["trig_16x"].text().strip()
            side.done_16x = ws["done_16x"].text().strip()
            side.plc_ip = ws["plc_ip"].text().strip()
            side.plc_port = ws["plc_port"].value()

        mats = []
        for r in range(self.tbl.rowCount()):
            name = (self.tbl.item(r, 0).text().strip()
                    if self.tbl.item(r, 0) else "")
            if not name:
                continue
            mats.append(MaterialConfig(name=name,
                                       heads_8x=_to_int(self.tbl.item(r, 1)),
                                       heads_16x=_to_int(self.tbl.item(r, 2))))
        c.materials = mats

    def _on_accept(self):
        self._collect()
        self.accept()

    def result_config(self):
        return self.cfg


def _to_int(item):
    try:
        return int(item.text().strip()) if item else 0
    except ValueError:
        return 0
