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

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QSpinBox, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from ..config import AppConfig, MaterialConfig, app_mode
from ..i18n import tr, set_language, current_language, available_languages
from ..material_import import parse_materials


def _section(title):
    """Nhãn tiêu đề nhóm trong form Setting."""
    lbl = QLabel(title)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color:#9fb4d8; font-weight:700; margin-top:6px;")
    return lbl


def _help(text):
    """Nhãn ghi chú dài: tự xuống dòng để không kéo rộng hộp thoại (trước đây
    chữ dài làm Setting rộng ra hoặc bị cắt khi màn hình nhỏ)."""
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color:#7f8b9e; font-size:12px;")
    return lbl


def _scroll(inner):
    """Bọc 1 trang tab trong vùng cuộn dọc.

    Tab dài (nhiều dòng cấu hình) sẽ cuộn được khi màn hình thấp thay vì bị
    tràn ra ngoài hộp thoại; cuộn ngang tắt để các ô nhập co theo bề ngang.
    """
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setFrameShape(QFrame.NoFrame)
    sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    sc.setWidget(inner)
    return sc


class SettingsDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = copy.deepcopy(cfg)     # làm việc trên bản sao
        self._orig_lang = current_language()   # để hoàn nguyên nếu bấm Hủy

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self._build_tabs()

        self.btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btns.accepted.connect(self._on_accept)
        self.btns.rejected.connect(self.reject)
        layout.addWidget(self.btns)
        self._apply_static_texts()
        self._apply_initial_size()

    def _apply_initial_size(self):
        """Mở hộp thoại vừa màn hình: cao tối đa = vùng hiển thị nên không bị
        tràn ra ngoài; mỗi tab đã có vùng cuộn riêng khi nội dung dài."""
        screen = self.screen() or QGuiApplication.primaryScreen()
        avail_h = screen.availableGeometry().height() if screen else 768
        self.setMaximumHeight(avail_h)
        self.resize(600, min(640, int(avail_h * 0.9)))

    # ------------------------------------------------------------------ #
    #  Dựng / đổi ngôn ngữ                                                #
    # ------------------------------------------------------------------ #
    def _build_tabs(self):
        """Dựng (hoặc dựng lại) toàn bộ tab theo ngôn ngữ hiện tại.

        Khi đổi ngôn ngữ, các chỉnh sửa đang nhập đã được _collect() lưu vào
        self.cfg trước đó nên dựng lại từ self.cfg sẽ không mất dữ liệu.
        """
        cur = self.tabs.currentIndex()
        self.tabs.blockSignals(True)
        while self.tabs.count():
            w = self.tabs.widget(0)
            self.tabs.removeTab(0)
            w.deleteLater()
        self.tabs.addTab(self._tab_general(), tr("Chung"))
        self.tabs.addTab(self._tab_plc(), tr("PLC"))
        self.tabs.addTab(self._tab_api(), tr("API MES"))
        self.tabs.addTab(self._tab_images(), tr("Tải ảnh"))
        self.tabs.addTab(self._tab_side("left"), tr("Bên trái"))
        self.tabs.addTab(self._tab_side("right"), tr("Bên phải"))
        self.tabs.addTab(self._tab_materials(), tr("Mã liệu"))
        if 0 <= cur < self.tabs.count():
            self.tabs.setCurrentIndex(cur)
        self.tabs.blockSignals(False)

    def _apply_static_texts(self):
        """Văn bản nằm ngoài tab (tiêu đề cửa sổ + nút OK/Hủy)."""
        self.setWindowTitle(tr("Setting"))
        self.btns.button(QDialogButtonBox.Ok).setText(tr("OK"))
        self.btns.button(QDialogButtonBox.Cancel).setText(tr("Hủy"))

    def _on_language_changed(self, *_):
        code = self.cbo_lang.currentData()
        if not code or code == current_language():
            return
        self._collect()                 # giữ lại chỉnh sửa đang nhập
        set_language(code)              # cập nhật cửa sổ chính + panel (qua listener)
        self._build_tabs()              # dựng lại dialog theo ngôn ngữ mới
        self._apply_static_texts()

    def reject(self):
        # Hoàn nguyên ngôn ngữ nếu người dùng đã xem trước rồi bấm Hủy.
        if current_language() != self._orig_lang:
            set_language(self._orig_lang)
        super().reject()

    # ------------------------------------------------------------------ #
    #  Tab Chung                                                          #
    # ------------------------------------------------------------------ #
    def _tab_general(self):
        w = QWidget(); form = QFormLayout(w)

        # --- Chọn ngôn ngữ giao diện (Việt / Trung / Anh) ---
        self.cbo_lang = QComboBox()
        for code, label in available_languages():
            self.cbo_lang.addItem(label, code)
        idx = self.cbo_lang.findData(getattr(self.cfg, "language", "vi"))
        if idx >= 0:
            self.cbo_lang.setCurrentIndex(idx)
        # nối tín hiệu SAU khi đặt sẵn mục hiện tại để không tự kích hoạt khi dựng
        self.cbo_lang.currentIndexChanged.connect(self._on_language_changed)
        form.addRow(tr("Ngôn ngữ:"), self.cbo_lang)

        self.cbo_mode = QComboBox()
        self.cbo_mode.addItem(tr("Giả lập (không cần PLC / tay scan)"), "sim")
        self.cbo_mode.addItem(tr("PLC thật + nhập SN tay (không cần tay scan)"),
                              "manual_sn")
        self.cbo_mode.addItem(tr("Thật (PLC + tay scan)"), "live")
        i = self.cbo_mode.findData(app_mode(self.cfg))
        self.cbo_mode.setCurrentIndex(i if i >= 0 else 0)
        form.addRow(tr("Chế độ:"), self.cbo_mode)

        self.spn_poll = QSpinBox(); self.spn_poll.setRange(20, 5000)
        self.spn_poll.setValue(self.cfg.poll_interval_ms)
        self.spn_poll.setSuffix(" ms")
        form.addRow(tr("Chu kỳ đọc PLC:"), self.spn_poll)

        # đường dẫn
        self.txt_base = QLineEdit(self.cfg.paths.base_dir)
        browse = QPushButton(tr("Chọn…"))
        browse.clicked.connect(self._browse_base)
        h = QHBoxLayout(); h.addWidget(self.txt_base, 1); h.addWidget(browse)
        hb = QWidget(); hb.setLayout(h)
        form.addRow(tr("Thư mục gốc dữ liệu:"), hb)

        self.txt_sub4 = QLineEdit(self.cfg.paths.sub_4x)
        self.txt_sub8 = QLineEdit(self.cfg.paths.sub_8x)
        self.txt_sub16 = QLineEdit(self.cfg.paths.sub_16x)
        self.txt_lglob = QLineEdit(self.cfg.paths.left_glob)
        self.txt_rglob = QLineEdit(self.cfg.paths.right_glob)
        form.addRow(tr("Thư mục con 4X:"), self.txt_sub4)
        form.addRow(tr("Thư mục con 8X:"), self.txt_sub8)
        form.addRow(tr("Thư mục con 16X:"), self.txt_sub16)
        form.addRow(tr("Mẫu tên file Trái:"), self.txt_lglob)
        form.addRow(tr("Mẫu tên file Phải:"), self.txt_rglob)
        form.addRow(_help(tr("Đường dẫn = <gốc>/<con 4X|8X|16X>/<YYYYMMDD>/CCD1*|CCD2*")))

        self.chk_today = QCheckBox(
            tr("Chỉ lấy dữ liệu của NGÀY HÔM NAY (báo lỗi nếu thiếu thư mục/file)"))
        self.chk_today.setChecked(self.cfg.paths.require_today)
        form.addRow(self.chk_today)
        return _scroll(w)

    def _browse_base(self):
        d = QFileDialog.getExistingDirectory(self, tr("Chọn thư mục gốc dữ liệu"),
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
        self.cbo_proto = QComboBox()
        self.cbo_proto.addItem("Mitsubishi SLMP", "slmp")
        self.cbo_proto.addItem("Modbus TCP", "modbus")
        ip_ = self.cbo_proto.findData(getattr(self.cfg.plc, "protocol", "slmp"))
        self.cbo_proto.setCurrentIndex(ip_ if ip_ >= 0 else 0)
        self.cbo_plc_code = QComboBox()
        self.cbo_plc_code.addItem("Binary", False)
        self.cbo_plc_code.addItem("ASCII", True)
        self.cbo_plc_code.setCurrentIndex(1 if getattr(self.cfg.plc, "ascii_mode", False) else 0)
        self.spn_modbus_unit = QSpinBox(); self.spn_modbus_unit.setRange(0, 255)
        self.spn_modbus_unit.setValue(getattr(self.cfg.plc, "modbus_unit", 255))
        form.addRow(tr("Giao thức:"), self.cbo_proto)
        form.addRow(tr("IP PLC chung:"), self.txt_plc_ip)
        form.addRow(tr("Port:"), self.spn_plc_port)
        form.addRow(tr("Timeout:"), self.spn_plc_to)
        form.addRow(tr("Data Code (SLMP):"), self.cbo_plc_code)
        form.addRow(tr("Modbus Unit ID:"), self.spn_modbus_unit)
        form.addRow(_help(tr("SLMP: Binary/ASCII phải KHỚP PLC. Modbus: Port "
                             "thường 502; D…→Holding Register, M…→Coil (số = địa "
                             "chỉ Modbus).")))
        form.addRow(_help(tr("Mỗi bên có thể đặt IP/Port riêng trong tab Bên trái/phải.")))

        # --- Test kết nối/đọc thử 1 thanh ghi ---
        form.addRow(_section(tr("Test kết nối PLC")))
        self.txt_plc_test = QLineEdit("D4206")
        self.txt_plc_test.setPlaceholderText(tr("vd D4206 (word) hoặc M100 (bit)"))
        btn_test = QPushButton(tr("Test đọc PLC"))
        btn_test.clicked.connect(self._test_plc)
        h = QHBoxLayout(); h.addWidget(self.txt_plc_test, 1); h.addWidget(btn_test)
        hw = QWidget(); hw.setLayout(h)
        form.addRow(tr("Đọc thử thanh ghi:"), hw)
        return _scroll(w)

    def _test_plc(self):
        """Đọc thử 1 thanh ghi. Ưu tiên KẾT NỐI CHUNG đang mở (tránh mở thêm
        kết nối thứ 2 tới PLC); nếu chưa có thì mở tạm theo cấu hình đang nhập."""
        from ..hardware.plc_client import PlcClient
        from ..hardware.mitsubishi_plc import is_word_device
        dev = (self.txt_plc_test.text().strip() or "D0")

        shared = getattr(self.parent(), "plc", None)
        if shared is not None and getattr(shared, "is_connected", False):
            try:
                val = (shared.read_word(dev) if is_word_device(dev)
                       else shared.read_bit(dev))
                QMessageBox.information(self, tr("Test PLC"),
                                       tr("(Kết nối chung) Đọc %s = %s") % (dev, val))
            except Exception as ex:           # noqa: BLE001
                QMessageBox.critical(self, tr("Test PLC"),
                                     tr("(Kết nối chung) Lỗi đọc %s:\n%s") % (dev, ex))
            return

        ip = self.txt_plc_ip.text().strip()
        port = self.spn_plc_port.value()
        if self.cbo_proto.currentData() == "modbus":
            from ..hardware.modbus_tcp import ModbusTcpClient
            cli = ModbusTcpClient(ip, port, self.spn_plc_to.value(),
                                  unit=self.spn_modbus_unit.value())
        else:
            cli = PlcClient(ip, port, self.spn_plc_to.value(),
                            ascii_mode=bool(self.cbo_plc_code.currentData()))
        try:
            val = cli.read_word(dev) if is_word_device(dev) else cli.read_bit(dev)
            QMessageBox.information(
                self, tr("Test PLC"),
                tr("Kết nối %s:%d OK.\nĐọc %s = %s") % (ip, port, dev, val))
        except Exception as ex:               # noqa: BLE001
            QMessageBox.critical(
                self, tr("Test PLC"),
                tr("Lỗi đọc %s từ %s:%d:\n%s") % (dev, ip, port, ex))
        finally:
            try:
                cli.close()
            except Exception:                 # noqa: BLE001
                pass

    # ------------------------------------------------------------------ #
    #  Tab API                                                            #
    # ------------------------------------------------------------------ #
    def _tab_api(self):
        w = QWidget(); form = QFormLayout(w)
        api = self.cfg.api

        # --- Tham số kết nối dùng chung cho mọi loại đầu ---
        form.addRow(_section(tr("Kết nối chung (mọi loại đầu)")))
        self.spn_api_to = QDoubleSpinBox(); self.spn_api_to.setRange(0.5, 60)
        self.spn_api_to.setValue(api.timeout); self.spn_api_to.setSuffix(" s")
        self.spn_retries = QSpinBox(); self.spn_retries.setRange(1, 10)
        self.spn_retries.setValue(api.retries)
        self.chk_verify = QCheckBox(tr("Kiểm tra chứng chỉ SSL"))
        self.chk_verify.setChecked(api.verify_ssl)
        self.txt_emp = QLineEdit(api.emp_no)
        self.txt_emp.setPlaceholderText(tr("vd V3081479"))
        self.chk_proxy = QCheckBox(tr("Đi qua proxy hệ thống"))
        self.chk_proxy.setChecked(api.use_proxy)
        self.txt_proxy = QLineEdit(api.proxy)
        self.txt_proxy.setPlaceholderText(tr("vd http://10.0.0.1:8080 (để trống = proxy hệ thống)"))
        form.addRow(tr("Timeout:"), self.spn_api_to)
        form.addRow(tr("Số lần retry:"), self.spn_retries)
        form.addRow(self.chk_verify)
        form.addRow(tr("Mã nhân viên (empNo):"), self.txt_emp)
        form.addRow(self.chk_proxy)
        form.addRow(tr("Proxy thủ công:"), self.txt_proxy)
        form.addRow(QLabel(tr("MES nội bộ: BỎ chọn proxy. Chỉ tích nếu MES nằm ngoài "
                              "mạng và phải qua proxy công ty.")))

        # --- API RIÊNG cho từng loại đầu: chọn đầu nào sẽ chạy theo API đó ---
        self._w_api = {}
        for label, head_cfg in (("4X", api.api_4x), ("8X", api.api_8x),
                                ("16X", api.api_16x)):
            form.addRow(_section(tr("API đầu %s — chọn đầu %s sẽ chạy theo API này")
                                 % (label, label)))
            self._w_api[label] = self._add_head_api_rows(form, head_cfg)
        form.addRow(_help(tr("Mỗi loại đầu có endpoint riêng. POST = tải kết quả; "
                             "GET kiểm tra SN tới <tiền tố>+SN+<hậu tố> (SN sai -> "
                             "CHẶN, không tải lên).")))
        form.addRow(_help(tr("POST body: sn + stationName (theo loại đầu) + empNo "
                             "+ timer (L1: v1 - v2 - ...; L2: ...).")))
        return _scroll(w)

    def _add_head_api_rows(self, form, head_cfg):
        """Thêm các dòng cấu hình API cho 1 loại đầu; trả về dict widget."""
        url = QLineEdit(head_cfg.url)
        post_ok = QLineEdit(head_cfg.post_ok_contains)
        post_ok.setPlaceholderText(tr("vd 200 (để trống = chỉ cần HTTP 2xx)"))
        station = QLineEdit(head_cfg.station_name)
        station.setPlaceholderText(tr("vd STATION-4X (mỗi loại đầu 1 tên khác nhau)"))
        chk = QCheckBox(tr("Bật kiểm tra SN bằng GET"))
        chk.setChecked(head_cfg.check_enabled)
        pre = QLineEdit(head_cfg.check_url_prefix)
        pre.setPlaceholderText(tr("vd http://mes/api/check?sn="))
        suf = QLineEdit(head_cfg.check_url_suffix)
        suf.setPlaceholderText(tr("vd &station=OP10 (có thể để trống)"))
        chk_ok = QLineEdit(head_cfg.check_ok_value)
        chk_ok.setPlaceholderText(tr("vd 0 — body BẰNG ĐÚNG giá trị này thì SN hợp lệ"))
        form.addRow(tr("URL POST (upload):"), url)
        form.addRow(tr("POST OK khi body chứa:"), post_ok)
        form.addRow(tr("Tên trạm (stationName):"), station)
        form.addRow(chk)
        form.addRow(tr("URL GET (tiền tố):"), pre)
        form.addRow(tr("URL GET (hậu tố):"), suf)
        form.addRow(tr("SN hợp lệ khi body bằng:"), chk_ok)
        return {"url": url, "post_ok_contains": post_ok, "station_name": station,
                "check_enabled": chk, "check_url_prefix": pre,
                "check_url_suffix": suf, "check_ok_value": chk_ok}

    # ------------------------------------------------------------------ #
    #  Tab Tải ảnh                                                        #
    # ------------------------------------------------------------------ #
    def _tab_images(self):
        w = QWidget(); form = QFormLayout(w)
        img = self.cfg.images

        self.chk_img = QCheckBox(tr("Bật tải ảnh AOI lên link đích"))
        self.chk_img.setChecked(img.enabled)
        form.addRow(self.chk_img)

        # --- Tham số dùng chung cho mọi loại đầu ---
        form.addRow(_section(tr("Cấu trúc thư mục ảnh (mọi loại đầu)")))
        self.txt_img_sub = QLineEdit(img.sub_image)
        self.txt_img_ok = QLineEdit(img.ok_dir)
        self.txt_img_ng = QLineEdit(img.ng_dir)
        self.txt_img_ext = QLineEdit(", ".join(img.extensions))
        form.addRow(tr("Thư mục con ảnh:"), self.txt_img_sub)
        form.addRow(tr("Thư mục ảnh OK:"), self.txt_img_ok)
        form.addRow(tr("Thư mục ảnh NG:"), self.txt_img_ng)
        form.addRow(tr("Phần mở rộng ảnh:"), self.txt_img_ext)
        form.addRow(_help(tr("Nguồn = <thư mục đầu>/<con ảnh>/<YYYY-MM-DD>/"
                             "<OK|NG>; đích = <link>/<YYYYMMDD>/.")))

        # --- Đường dẫn RIÊNG theo từng loại đầu ---
        self._w_img = {}
        for label, head_cfg in (("4X", img.img_4x), ("8X", img.img_8x),
                                ("16X", img.img_16x)):
            form.addRow(_section(tr("Ảnh đầu %s") % label))
            self._w_img[label] = self._add_head_image_rows(form, head_cfg)
        form.addRow(_help(tr("Đổi tên khi tải: <SN>_<YYYY.MM.DD HH.MM.SS>_Passed|"
                             "Failed_#<thứ tự đầu>.<ext> (vd 123456_2026.06.09 "
                             "18.34.15_Passed_#1.jpg; 2 đầu 8X -> _#1, _#2).")))
        return _scroll(w)

    def _add_head_image_rows(self, form, head_cfg):
        """Thêm dòng cấu hình ảnh (nguồn + link đích) cho 1 loại đầu."""
        src = QLineEdit(head_cfg.source_dir)
        src.setPlaceholderText(tr("vd D:/AOI/8X (chứa thư mục con Image)"))
        b_src = QPushButton(tr("Chọn…"))
        b_src.clicked.connect(lambda: self._browse_into(src))
        hs = QHBoxLayout(); hs.addWidget(src, 1); hs.addWidget(b_src)
        hsw = QWidget(); hsw.setLayout(hs)
        up = QLineEdit(head_cfg.upload_dir)
        up.setPlaceholderText(tr("vd //10.222.48.222/AOI/17G"))
        form.addRow(tr("Thư mục ảnh nguồn:"), hsw)
        form.addRow(tr("Link tải lên (đích):"), up)
        return {"source_dir": src, "upload_dir": up}

    def _browse_into(self, line_edit):
        d = QFileDialog.getExistingDirectory(self, tr("Chọn thư mục"),
                                             line_edit.text())
        if d:
            line_edit.setText(d)

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
        snr = QLineEdit(side.sn_result_reg)
        snr.setPlaceholderText(tr("vd D100 — ghi 1=OK / 2=NG (để trống = không ghi)"))
        pip = QLineEdit(side.plc_ip)
        pport = QSpinBox(); pport.setRange(0, 65535); pport.setValue(side.plc_port)

        form.addRow(tr("Cổng COM tay scan:"), port)
        form.addRow(tr("Baudrate:"), baud)
        form.addRow(tr("Tiền tố file (CCD):"), ccd)
        form.addRow(tr("Trigger 4X:"), t4)
        form.addRow(tr("Done 4X:"), d4)
        form.addRow(tr("Trigger 8X:"), t8)
        form.addRow(tr("Done 8X:"), d8)
        form.addRow(tr("Trigger 16X:"), t16)
        form.addRow(tr("Done 16X:"), d16)
        form.addRow(_help(tr("Trigger/Done nhận BIT (M…) hoặc thanh ghi WORD "
                             "(D…); word coi giá trị ≠ 0 là 'bật'.")))
        form.addRow(tr("Thanh ghi kết quả SN (1=OK/2=NG):"), snr)
        form.addRow(tr("PLC IP riêng (trống = chung):"), pip)
        form.addRow(tr("PLC Port riêng (0 = chung):"), pport)

        # lưu tham chiếu widget để đọc lại khi accept
        setattr(self, "_w_%s" % key, {
            "scanner_port": port, "scanner_baud": baud, "ccd_prefix": ccd,
            "trig_4x": t4, "done_4x": d4,
            "trig_8x": t8, "done_8x": d8, "trig_16x": t16, "done_16x": d16,
            "sn_result_reg": snr, "plc_ip": pip, "plc_port": pport,
        })
        return _scroll(w)

    # ------------------------------------------------------------------ #
    #  Tab Mã liệu                                                        #
    # ------------------------------------------------------------------ #
    def _tab_materials(self):
        w = QWidget(); v = QVBoxLayout(w)
        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(
            [tr("Chuyên án"), tr("Tên mã liệu"), tr("Số đầu 4X"),
             tr("Số đầu 8X"), tr("Số đầu 16X")])
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)   # Chuyên án
        hh.setSectionResizeMode(1, QHeaderView.Stretch)   # Tên mã liệu
        v.addWidget(self.tbl)
        for m in self.cfg.materials:
            self._add_material_row(m.project, m.name,
                                   m.heads_4x, m.heads_8x, m.heads_16x)

        h = QHBoxLayout()
        b_add = QPushButton(tr("Thêm mã liệu"))
        b_imp = QPushButton(tr("Nhập từ Excel…"))
        b_del = QPushButton(tr("Xóa dòng chọn"))
        b_add.clicked.connect(
            lambda: self._add_material_row(self._default_new_project(),
                                           "MÃ_MỚI", 0, 0, 0))
        b_imp.clicked.connect(self._import_materials)
        b_del.clicked.connect(self._del_material_row)
        h.addWidget(b_add); h.addWidget(b_imp); h.addWidget(b_del); h.addStretch(1)
        v.addLayout(h)
        v.addWidget(_help(tr(
            "Cột: Chuyên án | Tên mã liệu | Số đầu 4X / 8X / 16X (loại nào "
            "không có để trống = 0). Mỗi chuyên án gom nhiều mã liệu; ngoài "
            "giao diện chọn Chuyên án rồi mới chọn Mã liệu, và chỉ hiện đúng "
            "các loại đầu mà mã liệu có. Nhập từ Excel: trùng (chuyên án + tên) "
            "sẽ cập nhật, còn lại thêm mới.")))
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
            self, tr("Chọn file mã liệu (Excel/CSV)"), self.cfg.paths.base_dir,
            tr("Excel/CSV (*.xlsx *.xls *.xlsm *.csv);;Tất cả file (*)"))
        if not path:
            return
        try:
            materials, skipped = parse_materials(path)
        except Exception as ex:               # noqa: BLE001
            QMessageBox.critical(self, tr("Nhập mã liệu"),
                                 tr("Không đọc được file:\n%s") % ex)
            return
        if not materials:
            QMessageBox.warning(
                self, tr("Nhập mã liệu"),
                tr("Không tìm thấy mã liệu hợp lệ trong file.\n"
                   "Cần cột Tên mã liệu + ít nhất 1 cột Số đầu 4X / 8X / 16X."))
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

        msg = tr("Đã nhập từ:\n%s\n\nThêm mới: %d — Cập nhật: %d") % (
            path, added, updated)
        if skipped:
            msg += tr("\nBỏ qua %d dòng không có tên mã.") % skipped
        QMessageBox.information(self, tr("Nhập mã liệu"), msg)

    # ------------------------------------------------------------------ #
    #  Đọc widget -> cấu hình                                             #
    # ------------------------------------------------------------------ #
    def _collect(self):
        c = self.cfg
        c.language = self.cbo_lang.currentData() or getattr(c, "language", "vi")
        mode = self.cbo_mode.currentData() or "sim"
        c.simulation = (mode == "sim")
        c.manual_sn = (mode == "manual_sn")
        c.poll_interval_ms = self.spn_poll.value()

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
        c.plc.protocol = self.cbo_proto.currentData() or "slmp"
        c.plc.ascii_mode = bool(self.cbo_plc_code.currentData())
        c.plc.modbus_unit = self.spn_modbus_unit.value()

        c.api.timeout = self.spn_api_to.value()
        c.api.retries = self.spn_retries.value()
        c.api.verify_ssl = self.chk_verify.isChecked()
        c.api.emp_no = self.txt_emp.text().strip()
        c.api.use_proxy = self.chk_proxy.isChecked()
        c.api.proxy = self.txt_proxy.text().strip()
        for label, head_cfg in (("4X", c.api.api_4x), ("8X", c.api.api_8x),
                                ("16X", c.api.api_16x)):
            ws = self._w_api[label]
            head_cfg.url = ws["url"].text().strip()
            head_cfg.post_ok_contains = ws["post_ok_contains"].text().strip()
            head_cfg.station_name = ws["station_name"].text().strip()
            head_cfg.check_enabled = ws["check_enabled"].isChecked()
            head_cfg.check_url_prefix = ws["check_url_prefix"].text().strip()
            head_cfg.check_url_suffix = ws["check_url_suffix"].text().strip()
            head_cfg.check_ok_value = ws["check_ok_value"].text().strip()

        ci = c.images
        ci.enabled = self.chk_img.isChecked()
        ci.sub_image = self.txt_img_sub.text().strip() or "Image"
        ci.ok_dir = self.txt_img_ok.text().strip() or "OK"
        ci.ng_dir = self.txt_img_ng.text().strip() or "NG"
        exts = []
        for e in self.txt_img_ext.text().replace(";", ",").split(","):
            # chấp nhận "jpg", ".jpg", "*.jpg", " .JPG " -> chuẩn hóa ".jpg"
            e = e.strip().lstrip("*").lstrip(".").strip().lower()
            if e:
                exts.append("." + e)
        ci.extensions = exts or [".jpg"]
        for label, head_cfg in (("4X", ci.img_4x), ("8X", ci.img_8x),
                                ("16X", ci.img_16x)):
            ws = self._w_img[label]
            head_cfg.source_dir = ws["source_dir"].text().strip()
            head_cfg.upload_dir = ws["upload_dir"].text().strip()

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
            side.sn_result_reg = ws["sn_result_reg"].text().strip()
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
