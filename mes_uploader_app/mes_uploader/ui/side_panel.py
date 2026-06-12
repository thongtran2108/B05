# -*- coding: utf-8 -*-
"""Panel cho 1 bên (Trái / Phải). Mỗi panel có 1 SideWorker + 1 tay scan riêng.

Bố cục dạng "card": chọn mã liệu/loại đầu → card SN → tiến độ → card kết quả
→ nút điều khiển → khu giả lập → BẢNG DỮ LIỆU (SN ↔ giá trị) + NHẬT KÝ.

Sự kiện từ worker (luồng nền) được đưa về luồng GUI an toàn qua signal Qt.
"""

from PySide6.QtCore import Qt, QObject, Signal, Slot
from PySide6.QtGui import QColor, QFont
import html as _html
import re as _re
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QComboBox, QFrame, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..config import head_count, manual_sn_entry
from ..core.side_worker import ST_IDLE, ST_WAIT_SCAN, ST_RUNNING, SideWorker
from ..hardware.scanner import SerialScanner
from ..i18n import tr
from .theme import GREEN, RED, AMBER, ELEV2, BORDER2, CAPTION

# Cột bảng (chuỗi nguồn tiếng Việt = khóa dịch). Dùng len() để đếm cột và
# tr() từng cột khi đặt nhãn header (xem _build_table / retranslate).
TABLE_COLS = ["SN", "Loại", "Đầu", "Judge", "Thời gian", "MES", "Giá trị (Data01..N)"]
MAX_TABLE_ROWS = 1000

# Các loại đầu hỗ trợ, theo thứ tự hiển thị (tăng dần). Thanh "LOẠI ĐẦU" chỉ
# hiện loại nào mà mã liệu đang chọn THỰC SỰ có (số đầu > 0).
HEAD_TYPES = ("4X", "8X", "16X")

# Nhãn hiển thị cho mã liệu chưa gán chuyên án (project rỗng) — gom nhóm chung.
PROJECT_DEFAULT_LABEL = "(Chung)"


class HeadProgress(QWidget):
    """Thanh tiến độ đầu đo dạng segment: mỗi đầu 1 ô, tô sáng khi xong."""

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(7)

        top = QHBoxLayout(); top.setContentsMargins(0, 0, 0, 0)
        self._cap = QLabel(tr("TIẾN ĐỘ ĐẦU ĐO")); self._cap.setObjectName("caption")
        cap = self._cap
        self.lbl_count = QLabel("0 / 1")
        self.lbl_count.setStyleSheet("font-weight:700; color:#e6eaf2;")
        self.lbl_count.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top.addWidget(cap); top.addStretch(1); top.addWidget(self.lbl_count)
        root.addLayout(top)

        self._segrow = QHBoxLayout(); self._segrow.setContentsMargins(0, 0, 0, 0)
        self._segrow.setSpacing(5)
        root.addLayout(self._segrow)

        self._segs = []
        self._total = 1
        self._done = 0
        self._rebuild()

    def _rebuild(self):
        while self._segrow.count():
            it = self._segrow.takeAt(0)
            if it.widget():
                it.widget().setParent(None)
        self._segs = []
        for _ in range(self._total):
            seg = QFrame(); seg.setObjectName("headSeg")
            seg.setFixedHeight(10)
            seg.setProperty("done", False)
            self._segrow.addWidget(seg)
            self._segs.append(seg)
        self._refresh()

    def _refresh(self):
        for i, seg in enumerate(self._segs):
            done = i < self._done
            if seg.property("done") != done:
                seg.setProperty("done", done)
                seg.style().unpolish(seg); seg.style().polish(seg)
        self.lbl_count.setText("%d / %d" % (self._done, self._total))

    def set_progress(self, done, total):
        total = max(1, int(total))
        if total != self._total:
            self._total = total
            self._done = min(done, total)
            self._rebuild()
            return
        self._done = max(0, min(int(done), total))
        self._refresh()

    def retranslate(self):
        self._cap.setText(tr("TIẾN ĐỘ ĐẦU ĐO"))


class _EventBridge(QObject):
    """Cầu nối: phát sự kiện worker (luồng nền) -> slot ở luồng GUI."""
    event = Signal(str, dict)


class SidePanel(QGroupBox):
    def __init__(self, side_key, cfg, parent=None):
        super().__init__(self._title_for(side_key), parent)
        self.setObjectName("panelLeft" if side_key == "left" else "panelRight")
        self.side_key = side_key
        self.cfg = cfg
        self.worker = None
        self.scanner = None
        self.shared_plc = None          # kết nối PLC DÙNG CHUNG (cửa sổ chính cấp)
        self._pending_mes = []          # các ô cột MES của SN đang chạy
        self._cur_state = ST_IDLE       # trạng thái cuối (để dựng lại khi đổi ngôn ngữ)
        self._plc_connected = None      # None = chưa biết, True/False = đã/ mất kết nối

        self._bold = QFont(); self._bold.setBold(True)
        self._bridge = _EventBridge()
        self._bridge.event.connect(self._on_event)

        self._build_ui()
        self._reload_projects()

    @staticmethod
    def _title_for(side_key):
        return (tr("BÊN TRÁI · CCD1") if side_key == "left"
                else tr("BÊN PHẢI · CCD2"))

    # ------------------------------------------------------------------ #
    #  Dựng widget                                                        #
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        # Bọc toàn bộ nội dung trong vùng cuộn: khi cửa sổ / màn hình thấp,
        # nội dung không bị tràn và khuất ở dưới mà hiện thanh cuộn dọc để
        # vẫn xem được bảng dữ liệu + nhật ký.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 18, 12, 12)
        outer.setSpacing(0)
        scroll = QScrollArea(); scroll.setObjectName("panelScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        content = QWidget(); content.setObjectName("panelScrollBody")
        scroll.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(0, 0, 4, 0)   # chừa 4px bên phải cho thanh cuộn
        root.setSpacing(9)

        # --- Chọn chuyên án + mã liệu + loại đầu ---
        sel = QHBoxLayout(); sel.setSpacing(14)

        proj_col = QVBoxLayout(); proj_col.setSpacing(6)
        self._cap_project = QLabel(tr("CHUYÊN ÁN")); self._cap_project.setObjectName("caption")
        self.cbo_project = QComboBox()
        self.cbo_project.setMinimumWidth(120)
        proj_col.addWidget(self._cap_project); proj_col.addWidget(self.cbo_project)
        sel.addLayout(proj_col, 1)

        mat_col = QVBoxLayout(); mat_col.setSpacing(6)
        self._cap_material = QLabel(tr("MÃ LIỆU")); self._cap_material.setObjectName("caption")
        self.cbo_material = QComboBox()
        self.cbo_material.setMinimumWidth(120)
        mat_col.addWidget(self._cap_material); mat_col.addWidget(self.cbo_material)
        sel.addLayout(mat_col, 1)

        type_col = QVBoxLayout(); type_col.setSpacing(6)
        self._cap_type = QLabel(tr("LOẠI ĐẦU")); self._cap_type.setObjectName("caption")
        type_cap = self._cap_type
        seg_group = QFrame(); seg_group.setObjectName("segGroup")
        seg_lay = QHBoxLayout(seg_group)
        seg_lay.setContentsMargins(3, 3, 3, 3); seg_lay.setSpacing(3)
        self.type_group = QButtonGroup(self)
        self.type_group.setExclusive(True)
        self._type_btns = {}
        for label in HEAD_TYPES:
            b = QPushButton(label); b.setObjectName("segBtn")
            b.setCheckable(True); b.setCursor(Qt.PointingHandCursor)
            seg_lay.addWidget(b)
            self.type_group.addButton(b)
            self._type_btns[label] = b
        self._type_btns["8X"].setChecked(True)
        type_col.addWidget(type_cap); type_col.addWidget(seg_group)
        sel.addLayout(type_col)
        root.addLayout(sel)
        self.cbo_project.currentIndexChanged.connect(self._on_project_changed)
        self.cbo_material.currentIndexChanged.connect(self._on_material_changed)
        self.type_group.buttonClicked.connect(self._selection_changed)

        # --- Trạng thái + đèn PLC (chip) ---
        srow = QHBoxLayout(); srow.setSpacing(9)
        plc_chip = QFrame(); plc_chip.setObjectName("chip")
        pcl = QHBoxLayout(plc_chip); pcl.setContentsMargins(11, 7, 13, 7)
        self.lbl_plc = QLabel(); self.lbl_plc.setObjectName("chipText")
        pcl.addWidget(self.lbl_plc)
        state_chip = QFrame(); state_chip.setObjectName("chip")
        scl = QHBoxLayout(state_chip); scl.setContentsMargins(11, 7, 13, 7)
        self.lbl_state = QLabel(); self.lbl_state.setObjectName("chipText")
        scl.addWidget(self.lbl_state)
        self._render_plc()              # "● PLC: --"
        self._render_state()            # "Trạng thái: chưa bật"
        srow.addWidget(plc_chip)
        srow.addStretch(1)
        srow.addWidget(state_chip)
        root.addLayout(srow)

        # --- Card SN ---
        sn_card = QFrame(); sn_card.setObjectName("snCard")
        sc = QVBoxLayout(sn_card)
        sc.setContentsMargins(14, 12, 14, 13); sc.setSpacing(3)
        self._cap_sn = QLabel(tr("SERIAL NUMBER")); self._cap_sn.setObjectName("caption")
        cap = self._cap_sn
        cap.setAlignment(Qt.AlignCenter)
        self.lbl_sn = QLabel("——"); self.lbl_sn.setObjectName("snValue")
        self.lbl_sn.setAlignment(Qt.AlignCenter)
        sc.addWidget(cap); sc.addWidget(self.lbl_sn)
        root.addWidget(sn_card)

        # --- Tiến độ đầu đo (segment) ---
        self.progress = HeadProgress()
        self.progress.set_progress(0, 1)
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
        self.btn_start = QPushButton("▶  " + tr("Bắt đầu")); self.btn_start.setObjectName("startBtn")
        self.btn_stop = QPushButton("■  " + tr("Dừng")); self.btn_stop.setObjectName("stopBtn")
        self.btn_stop.setEnabled(False)
        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop.clicked.connect(self._on_stop)
        brow.addWidget(self.btn_start); brow.addWidget(self.btn_stop)
        root.addLayout(brow)

        # --- Khu nhập SN tay + giả lập tín hiệu PLC ---
        # Ô SN + nút "Quét" hiện khi nhập SN tay (giả lập HOẶC PLC thật + SN tay).
        # Nút "Tín hiệu PLC (giả lập)" chỉ hiện khi PLC giả lập (Mock).
        self.sim_box = QFrame()
        sbl = QHBoxLayout(self.sim_box)
        sbl.setContentsMargins(0, 0, 0, 0)
        self.txt_sn = QLineEdit(); self.txt_sn.setPlaceholderText(tr("Nhập SN giả lập…"))
        self.btn_scan = QPushButton(tr("Quét (giả lập)")); self.btn_scan.setObjectName("ghostBtn")
        self.btn_trig = QPushButton(tr("Tín hiệu PLC (giả lập)")); self.btn_trig.setObjectName("ghostBtn")
        self.btn_scan.clicked.connect(self._on_sim_scan)
        self.btn_trig.clicked.connect(self._on_sim_trigger)
        self.txt_sn.returnPressed.connect(self._on_sim_scan)
        sbl.addWidget(self.txt_sn, 1)
        sbl.addWidget(self.btn_scan)
        sbl.addWidget(self.btn_trig)
        root.addWidget(self.sim_box)
        self.sim_box.setVisible(manual_sn_entry(self.cfg))
        self.btn_trig.setVisible(self.cfg.simulation)

        # --- Splitter: BẢNG DỮ LIỆU (trên) + NHẬT KÝ (dưới) ---
        split = QSplitter(Qt.Vertical)

        tbox = QWidget(); tlay = QVBoxLayout(tbox)
        tlay.setContentsMargins(0, 0, 0, 0); tlay.setSpacing(4)
        thead = QHBoxLayout()
        self._cap_table = QLabel(tr("BẢNG DỮ LIỆU")); self._cap_table.setObjectName("caption")
        tcap = self._cap_table
        self.btn_clear = QPushButton(tr("Xóa bảng")); self.btn_clear.setObjectName("ghostBtn")
        self.btn_clear.setFixedWidth(96)
        self.btn_clear.clicked.connect(self._clear_table)
        thead.addWidget(tcap); thead.addStretch(1); thead.addWidget(self.btn_clear)
        tlay.addLayout(thead)
        self.table = self._build_table()
        tlay.addWidget(self.table)
        split.addWidget(tbox)

        lbox = QWidget(); llay = QVBoxLayout(lbox)
        llay.setContentsMargins(0, 0, 0, 0); llay.setSpacing(4)
        self._cap_log = QLabel(tr("NHẬT KÝ")); self._cap_log.setObjectName("caption")
        lcap = self._cap_log
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(800)
        self.log.setMinimumHeight(96)
        llay.addWidget(lcap); llay.addWidget(self.log)
        split.addWidget(lbox)

        split.setStretchFactor(0, 3); split.setStretchFactor(1, 2)
        split.setChildrenCollapsible(False)
        split.setSizes([300, 220])
        # Cao tối thiểu vừa đủ để bảng + nhật ký luôn dùng được; thấp hơn nữa
        # thì vùng cuộn của panel sẽ tiếp quản (không cắt mất nội dung).
        split.setMinimumHeight(240)
        root.addWidget(split, 1)

    def _build_table(self):
        t = QTableWidget(0, len(TABLE_COLS))
        t.setHorizontalHeaderLabels([tr(c) for c in TABLE_COLS])
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
        self.sim_box.setVisible(manual_sn_entry(cfg))
        self.btn_trig.setVisible(cfg.simulation)
        self._reload_projects()

    def set_plc(self, plc):
        """Nhận kết nối PLC DÙNG CHUNG từ cửa sổ chính."""
        self.shared_plc = plc

    def _project_items(self):
        """Danh sách (value, label) các chuyên án theo thứ tự xuất hiện.

        value = chuỗi project gốc ('' = nhóm chung), label = chuỗi hiển thị.
        """
        items, seen = [], set()
        for m in self.cfg.materials:
            val = m.project or ""
            if val not in seen:
                seen.add(val)
                items.append((val, val if val else tr(PROJECT_DEFAULT_LABEL)))
        if not items:
            items.append(("", tr(PROJECT_DEFAULT_LABEL)))
        return items

    def _current_project(self):
        val = self.cbo_project.currentData()
        return val if val is not None else ""

    def _reload_projects(self):
        """Nạp danh sách chuyên án vào combo, rồi nạp mã liệu của chuyên án đó."""
        cur = self.cbo_project.currentData()
        self.cbo_project.blockSignals(True)
        self.cbo_project.clear()
        for value, label in self._project_items():
            self.cbo_project.addItem(label, value)
        if cur is not None:
            idx = self.cbo_project.findData(cur)
            if idx >= 0:
                self.cbo_project.setCurrentIndex(idx)
        self.cbo_project.blockSignals(False)
        self._reload_materials()

    def _reload_materials(self):
        """Nạp mã liệu thuộc chuyên án đang chọn vào combo mã liệu."""
        cur = self.cbo_material.currentText()
        proj = self._current_project()
        self.cbo_material.blockSignals(True)
        self.cbo_material.clear()
        for m in self.cfg.materials:
            if (m.project or "") == proj:
                self.cbo_material.addItem(m.name)
        idx = self.cbo_material.findText(cur)
        if idx >= 0:
            self.cbo_material.setCurrentIndex(idx)
        self.cbo_material.blockSignals(False)
        self._update_type_buttons()

    def _current_material(self):
        name = self.cbo_material.currentText()
        proj = self._current_project()
        for m in self.cfg.materials:
            if m.name == name and (m.project or "") == proj:
                return m
        return None

    def _current_type(self):
        for label in HEAD_TYPES:
            if self._type_btns[label].isChecked():
                return label
        for label in HEAD_TYPES:            # dự phòng: nút đang hiện đầu tiên
            if self._type_btns[label].isVisible():
                return label
        return HEAD_TYPES[0]

    def _update_type_buttons(self):
        """Chỉ hiển thị các loại đầu mà mã liệu đang chọn THỰC SỰ có (số đầu > 0).

        Mã liệu chỉ có 4X -> chỉ hiện nút 4X; chỉ có 8X+16X -> chỉ hiện 8X và
        16X... Nếu mã liệu chưa khai báo số đầu nào (toàn 0) thì hiện tất cả để
        người dùng còn thấy lựa chọn.
        """
        material = self._current_material()
        avail = [t for t in HEAD_TYPES if head_count(material, t) > 0]
        if not avail:
            avail = list(HEAD_TYPES)
        cur = self._current_type()
        if cur not in avail:
            cur = avail[0]
        self.type_group.blockSignals(True)
        for label, btn in self._type_btns.items():
            btn.setVisible(label in avail)
        self._type_btns[cur].setChecked(True)
        self.type_group.blockSignals(False)

    # ------------------------------------------------------------------ #
    #  Bắt đầu / Dừng worker                                              #
    # ------------------------------------------------------------------ #
    def _on_start(self):
        material = self._current_material()
        head_type = self._current_type()
        if material is None:
            self._append_log(tr("Chưa chọn mã liệu. Vào Setting > Mã liệu để thêm."))
            return
        n = head_count(material, head_type)
        if n <= 0:
            self._append_log(tr("Mã liệu '%s' không có đầu %s.") % (material.name, head_type))
            return

        side_cfg = getattr(self.cfg, self.side_key)
        plc = self.shared_plc
        if plc is None:
            self._append_log(tr("Chưa có kết nối PLC."))
            return
        # Chế độ thật: BẮT BUỘC đã kết nối PLC chung trước khi chạy.
        if not self.cfg.simulation and not getattr(plc, "is_connected", False):
            self._append_log(tr("Hãy bấm 'Kết nối PLC' trước khi Bắt đầu."))
            return
        # Dùng kết nối PLC CHUNG -> worker KHÔNG đóng khi dừng (owns_plc=False).
        self.worker = SideWorker(self.side_key, self.cfg, plc, self._emit_event,
                                 owns_plc=False)
        self.worker.start()
        self.worker.arm(material, head_type)

        # Chỉ mở tay scan COM khi KHÔNG nhập SN tay (chế độ thật đầy đủ).
        if not manual_sn_entry(self.cfg):
            self.scanner = SerialScanner(
                side_cfg.scanner_port, side_cfg.scanner_baud,
                on_scan=lambda sn: self.worker.submit_sn(sn),
                on_error=lambda msg: self._emit_event("log", text=msg))
            self.scanner.start()

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.cbo_project.setEnabled(False)
        self.cbo_material.setEnabled(False)

    def _on_stop(self):
        self.stop_worker()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.cbo_project.setEnabled(True)
        self.cbo_material.setEnabled(True)
        self._cur_state = "STOPPED"
        self._render_state()

    def stop_worker(self):
        if self.scanner:
            self.scanner.stop(); self.scanner = None
        if self.worker:
            self.worker.disarm(); self.worker.stop(); self.worker = None

    # ------------------------------------------------------------------ #
    #  Lựa chọn / giả lập / bảng                                          #
    # ------------------------------------------------------------------ #
    def _on_project_changed(self, *_):
        # Đổi chuyên án -> nạp lại danh sách mã liệu của chuyên án đó, rồi báo worker.
        self._reload_materials()
        self._selection_changed()

    def _on_material_changed(self, *_):
        # Đổi mã liệu -> cập nhật lại các nút loại đầu hiển thị, rồi báo worker.
        self._update_type_buttons()
        self._selection_changed()

    def _selection_changed(self, *_):
        if self.worker:
            self.worker.set_selection(self._current_material(), self._current_type())

    def _on_sim_scan(self):
        sn = self.txt_sn.text().strip()
        if not sn:
            return
        if not self.worker:
            self._append_log(tr("Chưa bấm 'Bắt đầu'."))
            return
        self.worker.submit_sn(sn)
        self.txt_sn.clear()

    def _on_sim_trigger(self):
        if not self.worker:
            self._append_log(tr("Chưa bấm 'Bắt đầu'."))
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
            # text đã được worker dịch sẵn theo ngôn ngữ hiện tại khi phát sự kiện
            self.lbl_state.setText("%s: %s" % (tr("Trạng thái"), data.get("text", "")))
        elif etype == "sn":
            self.lbl_sn.setText(data.get("sn", "——"))
            self._set_result_style(None)
            self.lbl_result.setText("…")
            self._pending_mes = []        # bắt đầu nhóm hàng cho SN mới
        elif etype == "progress":
            done = data.get("done", 0); total = max(1, data.get("total", 1))
            self.progress.set_progress(done, total)
        elif etype == "reading":
            self._add_reading_row(data)
        elif etype == "error":
            self._show_error(data)
        elif etype == "sn_rejected":
            self._show_rejected(data)
        elif etype == "result":
            self._show_result(data.get("result", ""), data.get("ok", False))
            self._mark_uploaded(data.get("result", ""), data.get("ok", False))
        elif etype == "plc":
            self._set_plc(data.get("connected", False))
        elif etype == "state":
            self._cur_state = data.get("state", "")
            self._render_state()

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

    def _cap_rows(self):
        """Giới hạn số dòng bảng (chạy dài không phình bộ nhớ)."""
        t = self.table
        while t.rowCount() > MAX_TABLE_ROWS:
            t.removeRow(0)

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
                it.setToolTip(tr("%d giá trị:\n%s") % (len(vals), vals_str))
            t.setItem(r, c, it)

        jitem = t.item(r, 3)
        jitem.setForeground(QColor(GREEN if judge == "OK" else RED))
        jitem.setFont(self._bold)
        if judge != "OK":
            for c in range(t.columnCount()):
                t.item(r, c).setBackground(QColor("#2a1e22"))

        self._pending_mes.append(t.item(r, 5))
        t.scrollToBottom()
        self._cap_rows()

    def _mark_uploaded(self, result, ok):
        for it in self._pending_mes:
            if it is None:
                continue
            it.setText("✔" if ok else "✗")
            it.setTextAlignment(Qt.AlignCenter)
            it.setForeground(QColor(GREEN if ok else AMBER))
            it.setToolTip(tr("Đã gửi MES (result=%s)") % result if ok
                          else tr("Gửi MES lỗi — xem nhật ký"))
        self._pending_mes = []

    def _show_error(self, d):
        """Hiển thị lỗi thiếu dữ liệu: banner đỏ + 1 dòng LỖI trong bảng."""
        msg = str(d.get("message", "")).replace("\n", " ")
        self.lbl_result.setText(tr("LỖI DỮ LIỆU"))
        self.lbl_result.setStyleSheet(
            "background:#a3282d; color:#ffecec; border-radius:10px; font-weight:800;")
        self.lbl_state.setText("%s: %s — %s" % (tr("Trạng thái"), tr("LỖI"), msg))

        t = self.table
        r = t.rowCount(); t.insertRow(r)
        texts = [str(d.get("sn", "")), str(d.get("head_type", "")),
                 "%d/%d" % (d.get("index", 0), d.get("total", 0)),
                 tr("LỖI"), "—", "—", msg]
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
        self._cap_rows()
        self._pending_mes = []          # SN bị hủy, không có gì để đánh dấu MES

    def _show_rejected(self, d):
        """SN bị CHẶN ở bước kiểm tra GET: banner hổ phách + dòng CHẶN trong bảng."""
        sn = str(d.get("sn", ""))
        msg = str(d.get("message", "")).replace("\n", " ")
        self.lbl_sn.setText(sn)
        self.lbl_result.setText(tr("SN BỊ CHẶN"))
        self.lbl_result.setStyleSheet(
            "background:#9c6b1f; color:#fff; border-radius:10px; font-weight:800;")

        t = self.table
        r = t.rowCount(); t.insertRow(r)
        texts = [sn, "—", "—", tr("CHẶN"), "—", "—", msg]
        for c, txt in enumerate(texts):
            it = QTableWidgetItem(txt)
            if c in (1, 2, 3, 5):
                it.setTextAlignment(Qt.AlignCenter)
            if c == 6:
                it.setToolTip(msg)
            it.setBackground(QColor("#2a241a"))
            t.setItem(r, c, it)
        jitem = t.item(r, 3)
        jitem.setForeground(QColor(AMBER)); jitem.setFont(self._bold)
        t.scrollToBottom()
        self._cap_rows()
        self._pending_mes = []

    # ------------------------------------------------------------------ #
    #  Helper hiển thị                                                    #
    # ------------------------------------------------------------------ #
    def _append_log(self, text):
        if not text:
            return
        for line in str(text).split("\n"):
            self.log.appendHtml(self._colorize_log(line))

    @staticmethod
    def _colorize_log(line):
        """Tô màu 1 dòng nhật ký: đỏ = NG/LỖI, hổ phách = chặn/gửi lỗi,
        xanh = OK/thành công."""
        safe = _html.escape(line).replace("  ", "&nbsp;&nbsp;")
        low = line.lower()
        color = "#9aa6b6"      # mặc định
        weight = "400"

        # Từ khóa đa ngôn ngữ (Việt / Anh / Trung) để tô màu nhật ký dù đang ở
        # ngôn ngữ nào. So khớp theo low.lower() nên dùng chữ thường.
        red_kw = ("lỗi", "that bai", "thất bại", "[fail]", "fail", "✗",
                  "không hợp lệ", "mất kết nối", "error", "exception",
                  "timeout", "thiếu", "huỷ", "hủy",
                  "invalid", "disconnected", "failed", "cancel",
                  "错误", "失败", "无效", "连接断开", "取消")
        amber_kw = ("chặn", "gửi lỗi", "retry", "thử lại", "cảnh báo", "bỏ qua",
                    "blocked", "warning", "skip",
                    "拦截", "重试", "警告", "跳过", "已忽略")
        green_kw = ("thành công", "✓", "hoàn thành", "hợp lệ",
                    "success", "completed", "valid", "accepted",
                    "成功", "完成", "有效", "接收成功")

        is_ng = bool(_re.search(r"\bNG\b", line))
        is_ok = bool(_re.search(r"\bOK\b", line)) or any(k in low for k in green_kw)

        if is_ng or any(k in low for k in red_kw):
            color = "#ff6b68"; weight = "600"
        elif any(k in low for k in amber_kw):
            color = "#e6b765"; weight = "600"
        elif is_ok:
            color = "#5fe0a0"
        elif line.lstrip().startswith(("→", "->", "▶")):
            color = "#7fb0ff"

        return '<span style="color:%s; font-weight:%s;">%s</span>' % (color, weight, safe)

    def _set_plc(self, connected):
        self._plc_connected = connected
        self._render_plc()

    def _render_plc(self):
        """Dựng lại chip PLC theo trạng thái đã lưu (để đổi ngôn ngữ được)."""
        if self._plc_connected is None:
            self.lbl_plc.setText("● PLC: --")
            self.lbl_plc.setStyleSheet("")
        elif self._plc_connected:
            self.lbl_plc.setText("● PLC: " + tr("kết nối"))
            self.lbl_plc.setStyleSheet("color: %s; font-size:12px; font-weight:600;" % GREEN)
        else:
            self.lbl_plc.setText("● PLC: " + tr("mất kết nối"))
            self.lbl_plc.setStyleSheet("color: %s; font-size:12px; font-weight:600;" % RED)

    def _render_state(self):
        """Dựng lại chip trạng thái theo trạng thái đã lưu (mapped)."""
        mapping = {ST_IDLE: "chưa bật", ST_WAIT_SCAN: "chờ quét mã",
                   ST_RUNNING: "đang chạy", "STOPPED": "đã dừng"}
        word = mapping.get(self._cur_state, self._cur_state)
        self.lbl_state.setText("%s: %s" % (tr("Trạng thái"), tr(word)))

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
            self.lbl_result.setText(res + " " + tr("(gửi lỗi)"))
            self.lbl_result.setStyleSheet(
                "background:#9c6b1f; color:#fff; border-radius:10px; font-weight:800;")
        else:
            self.lbl_result.setText("OK" if res == "OK" else "NG")
            self._set_result_style(res == "OK")

    # ------------------------------------------------------------------ #
    #  Đổi ngôn ngữ                                                       #
    # ------------------------------------------------------------------ #
    def retranslate(self):
        """Cập nhật lại văn bản tĩnh của panel khi đổi ngôn ngữ.

        Các dòng đã ghi trong bảng/nhật ký là lịch sử nên giữ nguyên; nội dung
        phát sinh mới sẽ theo ngôn ngữ vừa chọn.
        """
        self.setTitle(self._title_for(self.side_key))
        self._cap_project.setText(tr("CHUYÊN ÁN"))
        self._cap_material.setText(tr("MÃ LIỆU"))
        self._cap_type.setText(tr("LOẠI ĐẦU"))
        self._cap_sn.setText(tr("SERIAL NUMBER"))
        self._cap_table.setText(tr("BẢNG DỮ LIỆU"))
        self._cap_log.setText(tr("NHẬT KÝ"))
        self.progress.retranslate()
        self.btn_start.setText("▶  " + tr("Bắt đầu"))
        self.btn_stop.setText("■  " + tr("Dừng"))
        self.btn_scan.setText(tr("Quét (giả lập)"))
        self.btn_trig.setText(tr("Tín hiệu PLC (giả lập)"))
        self.btn_clear.setText(tr("Xóa bảng"))
        self.txt_sn.setPlaceholderText(tr("Nhập SN giả lập…"))
        self.table.setHorizontalHeaderLabels([tr(c) for c in TABLE_COLS])
        self._render_plc()
        self._render_state()
        self._reload_projects()         # cập nhật nhãn "(Chung)" của chuyên án
