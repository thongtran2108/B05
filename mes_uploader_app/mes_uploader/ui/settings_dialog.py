# -*- coding: utf-8 -*-
"""Hộp thoại Setting: chỉnh toàn bộ cấu hình và quản lý mã liệu.

Gồm các tab:
  - Chung   : chế độ giả lập, chu kỳ poll, đường dẫn thư mục dữ liệu
  - PLC     : IP / Port / timeout của PLC chung
  - API MES : URL, timeout, số lần retry, định dạng trường data
  - Bên trái / Bên phải : cổng COM tay scan, tiền tố CCD, địa chỉ bit handshake
  - Mã liệu : bảng thêm/sửa/xóa mã liệu (chuyên án + tên + số đầu 4X/8X/16X);
              mỗi chuyên án gom nhiều mã liệu, kèm nút nhập từ Excel/CSV
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

        self.txt_sub4 = QLineEdit(self.cfg.paths.sub_4x)
        self.txt_sub8 = QLineEdit(self.cfg.paths.sub_8x)
        self.txt_sub16 = QLineEdit(self.cfg.paths.sub_16x)
        self.txt_lglob = QLineEdit(self.cfg.paths.left_glob)
        self.txt_rglob = QLineEdit(self.cfg.paths.right_glob)
        form.addRow("Thư mục con 4X:", self.txt_sub4)
        form.addRow("Thư mục con 8X:", self.txt_sub8)
        form.addRow("Thư mục con 16X:", self.txt_sub16)
        form.addRow("Mẫu tên file Trái:", self.txt_lglob)
        form.addRow("Mẫu tên file Phải:", self.txt_rglob)
        form.addRow(QLabel("Đường dẫn = <gốc>/<con 4X|8X|16X>/<YYYYMMDD>/CCD1*|CCD2*"))

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
        api = self.cfg.api

        # --- Tham số kết nối dùng chung cho mọi loại đầu ---
        form.addRow(_section("Kết nối chung (mọi loại đầu)"))
        self.spn_api_to = QDoubleSpinBox(); self.spn_api_to.setRange(0.5, 60)
        self.spn_api_to.setValue(api.timeout); self.spn_api_to.setSuffix(" s")
        self.spn_retries = QSpinBox(); self.spn_retries.setRange(1, 10)
        self.spn_retries.setValue(api.retries)
        self.chk_verify = QCheckBox("Kiểm tra chứng chỉ SSL")
        self.chk_verify.setChecked(api.verify_ssl)
        self.cbo_fmt = QComboBox()
        self.cbo_fmt.addItems(["values_only", "full_row", "structured"])
        self.cbo_fmt.setCurrentText(api.data_format)
        self.chk_proxy = QCheckBox("Đi qua proxy hệ thống")
        self.chk_proxy.setChecked(api.use_proxy)
        self.txt_proxy = QLineEdit(api.proxy)
        self.txt_proxy.setPlaceholderText("vd http://10.0.0.1:8080 (để trống = proxy hệ thống)")
        form.addRow("Timeout:", self.spn_api_to)
        form.addRow("Số lần retry:", self.spn_retries)
        form.addRow(self.chk_verify)
        form.addRow("Định dạng trường data:", self.cbo_fmt)
        form.addRow(QLabel("values_only = chỉ Data01..N | full_row = cả dòng | "
                           "structured = key:value"))
        form.addRow(self.chk_proxy)
        form.addRow("Proxy thủ công:", self.txt_proxy)
        form.addRow(QLabel("MES nội bộ: BỎ chọn proxy. Chỉ tích nếu MES nằm ngoài "
                           "mạng và phải qua proxy công ty."))

        # --- API RIÊNG cho từng loại đầu: chọn đầu nào sẽ chạy theo API đó ---
        self._w_api = {}
        for label, head_cfg in (("4X", api.api_4x), ("8X", api.api_8x),
                                ("16X", api.api_16x)):
            form.addRow(_section("API đầu %s — chọn đầu %s sẽ chạy theo API này"
                                 % (label, label)))
            self._w_api[label] = self._add_head_api_rows(form, head_cfg)
        form.addRow(QLabel("Mỗi loại đầu có endpoint riêng. POST = tải kết quả; "
                           "GET kiểm tra SN tới <tiền tố>+SN+<hậu tố> (SN sai -> "
                           "CHẶN, không tải lên)."))

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(w)
        return scroll

    def _add_head_api_rows(self, form, head_cfg):
        """Thêm các dòng cấu hình API cho 1 loại đầu; trả về dict widget."""
        url = QLineEdit(head_cfg.url)
        post_ok = QLineEdit(head_cfg.post_ok_contains)
        post_ok.setPlaceholderText("vd 200 (để trống = chỉ cần HTTP 2xx)")
        chk = QCheckBox("Bật kiểm tra SN bằng GET")
        chk.setChecked(head_cfg.check_enabled)
        pre = QLineEdit(head_cfg.check_url_prefix)
        pre.setPlaceholderText("vd http://mes/api/check?sn=")
        suf = QLineEdit(head_cfg.check_url_suffix)
        suf.setPlaceholderText("vd &station=OP10 (có thể để trống)")
        chk_ok = QLineEdit(head_cfg.check_ok_contains)
        chk_ok.setPlaceholderText("vd 0 — body chứa chuỗi này thì SN hợp lệ")
        form.addRow("URL POST (upload):", url)
        form.addRow("POST OK khi body chứa:", post_ok)
        form.addRow(chk)
        form.addRow("URL GET (tiền tố):", pre)
        form.addRow("URL GET (hậu tố):", suf)
        form.addRow("SN hợp lệ khi body chứa:", chk_ok)
        return {"url": url, "post_ok_contains": post_ok, "check_enabled": chk,
                "check_url_prefix": pre, "check_url_suffix": suf,
                "check_ok_contains": chk_ok}

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
        t4 = QLineEdit(side.trig_4x); d4 = QLineEdit(side.done_4x)
        t8 = QLineEdit(side.trig_8x); d8 = QLineEdit(side.done_8x)
        t16 = QLineEdit(side.trig_16x); d16 = QLineEdit(side.done_16x)
        pip = QLineEdit(side.plc_ip)
        pport = QSpinBox(); pport.setRange(0, 65535); pport.setValue(side.plc_port)

        form.addRow("Cổng COM tay scan:", port)
        form.addRow("Baudrate:", baud)
        form.addRow("Tiền tố file (CCD):", ccd)
        form.addRow("Bit trigger 4X:", t4)
        form.addRow("Bit done 4X:", d4)
        form.addRow("Bit trigger 8X:", t8)
        form.addRow("Bit done 8X:", d8)
        form.addRow("Bit trigger 16X:", t16)
        form.addRow("Bit done 16X:", d16)
        form.addRow("PLC IP riêng (trống = chung):", pip)
        form.addRow("PLC Port riêng (0 = chung):", pport)

        # lưu tham chiếu widget để đọc lại khi accept
        setattr(self, "_w_%s" % key, {
            "scanner_port": port, "scanner_baud": baud, "ccd_prefix": ccd,
            "trig_4x": t4, "done_4x": d4,
            "trig_8x": t8, "done_8x": d8, "trig_16x": t16, "done_16x": d16,
            "plc_ip": pip, "plc_port": pport,
        })
        return w

    # ------------------------------------------------------------------ #
    #  Tab Mã liệu                                                        #
    # ------------------------------------------------------------------ #
    def _tab_materials(self):
        w = QWidget(); v = QVBoxLayout(w)
        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(
            ["Chuyên án", "Tên mã liệu", "Số đầu 4X", "Số đầu 8X", "Số đầu 16X"])
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)   # Chuyên án
        hh.setSectionResizeMode(1, QHeaderView.Stretch)   # Tên mã liệu
        v.addWidget(self.tbl)
        for m in self.cfg.materials:
            self._add_material_row(m.project, m.name,
                                   m.heads_4x, m.heads_8x, m.heads_16x)

        h = QHBoxLayout()
        b_add = QPushButton("Thêm mã liệu")
        b_imp = QPushButton("Nhập từ Excel…")
        b_del = QPushButton("Xóa dòng chọn")
        b_add.clicked.connect(
            lambda: self._add_material_row(self._default_new_project(),
                                           "MÃ_MỚI", 0, 0, 0))
        b_imp.clicked.connect(self._import_materials)
        b_del.clicked.connect(self._del_material_row)
        h.addWidget(b_add); h.addWidget(b_imp); h.addWidget(b_del); h.addStretch(1)
        v.addLayout(h)
        v.addWidget(QLabel(
            "Cột: Chuyên án | Tên mã liệu | Số đầu 4X / 8X / 16X (loại nào "
            "không có để trống = 0). Mỗi chuyên án gom nhiều mã liệu; ngoài "
            "giao diện chọn Chuyên án rồi mới chọn Mã liệu, và chỉ hiện đúng "
            "các loại đầu mà mã liệu có. Nhập từ Excel: trùng (chuyên án + tên) "
            "sẽ cập nhật, còn lại thêm mới."))
        return w

    def _add_material_row(self, project, name, h4, h8, h16):
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)
        self.tbl.setItem(r, 0, QTableWidgetItem(str(project)))
        self.tbl.setItem(r, 1, QTableWidgetItem(str(name)))
        self.tbl.setItem(r, 2, QTableWidgetItem(str(h4)))
        self.tbl.setItem(r, 3, QTableWidgetItem(str(h8)))
        self.tbl.setItem(r, 4, QTableWidgetItem(str(h16)))

    def _default_new_project(self):
        """Chuyên án gợi ý cho dòng mới = chuyên án của dòng cuối (cho dễ nhập)."""
        last = self.tbl.rowCount() - 1
        if last >= 0:
            it = self.tbl.item(last, 0)
            if it and it.text().strip():
                return it.text().strip()
        return "Chuyên án 1"

    def _del_material_row(self):
        r = self.tbl.currentRow()
        if r >= 0:
            self.tbl.removeRow(r)

    def _material_rows_by_key(self):
        """Map {(chuyên án, tên mã liệu) -> chỉ số dòng} của các mã trong bảng."""
        out = {}
        for r in range(self.tbl.rowCount()):
            it_p = self.tbl.item(r, 0); it_n = self.tbl.item(r, 1)
            proj = it_p.text().strip() if it_p else ""
            name = it_n.text().strip() if it_n else ""
            if name and (proj, name) not in out:
                out[(proj, name)] = r
        return out

    def _import_materials(self):
        """Chọn file Excel/CSV -> nạp mã liệu vào bảng (gộp theo chuyên án + tên)."""
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
                "Cần cột Tên mã liệu + ít nhất 1 cột Số đầu 4X / 8X / 16X.")
            return

        existing = self._material_rows_by_key()
        added = updated = 0
        for m in materials:
            key = (m.project or "", m.name)
            if key in existing:               # trùng (chuyên án + tên) -> cập nhật
                r = existing[key]
                self.tbl.setItem(r, 2, QTableWidgetItem(str(m.heads_4x)))
                self.tbl.setItem(r, 3, QTableWidgetItem(str(m.heads_8x)))
                self.tbl.setItem(r, 4, QTableWidgetItem(str(m.heads_16x)))
                updated += 1
            else:                             # mã mới -> thêm dòng
                self._add_material_row(m.project, m.name,
                                       m.heads_4x, m.heads_8x, m.heads_16x)
                existing[key] = self.tbl.rowCount() - 1
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
        c.paths.sub_4x = self.txt_sub4.text().strip()
        c.paths.sub_8x = self.txt_sub8.text().strip()
        c.paths.sub_16x = self.txt_sub16.text().strip()
        c.paths.left_glob = self.txt_lglob.text().strip() or "CCD1*"
        c.paths.right_glob = self.txt_rglob.text().strip() or "CCD2*"
        c.paths.require_today = self.chk_today.isChecked()

        c.plc.ip = self.txt_plc_ip.text().strip()
        c.plc.port = self.spn_plc_port.value()
        c.plc.timeout = self.spn_plc_to.value()

        c.api.timeout = self.spn_api_to.value()
        c.api.retries = self.spn_retries.value()
        c.api.verify_ssl = self.chk_verify.isChecked()
        c.api.data_format = self.cbo_fmt.currentText()
        c.api.use_proxy = self.chk_proxy.isChecked()
        c.api.proxy = self.txt_proxy.text().strip()
        for label, head_cfg in (("4X", c.api.api_4x), ("8X", c.api.api_8x),
                                ("16X", c.api.api_16x)):
            ws = self._w_api[label]
            head_cfg.url = ws["url"].text().strip()
            head_cfg.post_ok_contains = ws["post_ok_contains"].text().strip()
            head_cfg.check_enabled = ws["check_enabled"].isChecked()
            head_cfg.check_url_prefix = ws["check_url_prefix"].text().strip()
            head_cfg.check_url_suffix = ws["check_url_suffix"].text().strip()
            head_cfg.check_ok_contains = ws["check_ok_contains"].text().strip()

        for key in ("left", "right"):
            ws = getattr(self, "_w_%s" % key)
            side = getattr(c, key)
            side.scanner_port = ws["scanner_port"].text().strip()
            side.scanner_baud = ws["scanner_baud"].value()
            side.ccd_prefix = ws["ccd_prefix"].currentText()
            side.trig_4x = ws["trig_4x"].text().strip()
            side.done_4x = ws["done_4x"].text().strip()
            side.trig_8x = ws["trig_8x"].text().strip()
            side.done_8x = ws["done_8x"].text().strip()
            side.trig_16x = ws["trig_16x"].text().strip()
            side.done_16x = ws["done_16x"].text().strip()
            side.plc_ip = ws["plc_ip"].text().strip()
            side.plc_port = ws["plc_port"].value()

        mats = []
        for r in range(self.tbl.rowCount()):
            name = (self.tbl.item(r, 1).text().strip()
                    if self.tbl.item(r, 1) else "")
            if not name:
                continue
            project = (self.tbl.item(r, 0).text().strip()
                       if self.tbl.item(r, 0) else "")
            mats.append(MaterialConfig(name=name, project=project,
                                       heads_4x=_to_int(self.tbl.item(r, 2)),
                                       heads_8x=_to_int(self.tbl.item(r, 3)),
                                       heads_16x=_to_int(self.tbl.item(r, 4))))
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
