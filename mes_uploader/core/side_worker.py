# -*- coding: utf-8 -*-
"""Máy trạng thái lưu trình cho 1 bên (Trái / Phải) — chạy trên luồng riêng.

Lưu trình (giống nhau cho cả 2 bên, nhưng độc lập):

  1. Người dùng chọn mã liệu + loại đầu (8X / 16X) rồi bấm "Bắt đầu" (arm).
  2. Quét SN bằng tay scan của bên đó  -> submit_sn(sn).
  3. Số lần chạy = số đầu của loại đã chọn (vd ABC có 2 đầu 8X -> 2 lần).
  4. Mỗi lần PLC bật bit trigger (sườn lên 0->1):
        - đọc DÒNG MỚI NHẤT trong file của bên (CCD1 trái / CCD2 phải)
        - ghi bit 'done' = 1 báo hoàn thành về PLC, chờ PLC nhả trigger, hạ done
  5. Khi đủ số đầu -> GỘP dữ liệu -> POST 1 lần lên MES -> quay lại chờ quét.

Module này KHÔNG phụ thuộc PySide6: phát sự kiện qua callback on_event(type,
**data). Lớp giao diện sẽ marshal các sự kiện này về luồng GUI bằng signal.
"""

import os
import queue
import threading
import time

from .. import data_reader, mes_api
from ..config import side_addresses, head_count
from ..hardware.plc_client import MockPlcClient


# Các trạng thái
ST_IDLE = "IDLE"            # chưa bật (chưa arm)
ST_WAIT_SCAN = "WAIT_SCAN"  # đã bật, đang chờ quét SN
ST_RUNNING = "RUNNING"      # đã có SN, đang chờ/tiếp nhận tín hiệu chạy


class SideWorker:
    def __init__(self, side_key, cfg, plc_client, on_event):
        self.side_key = side_key            # 'left' | 'right'
        self.cfg = cfg
        self.plc = plc_client
        self.on_event = on_event            # callable(event_type, **data)

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._sn_queue = queue.Queue()

        self._armed = False
        self._state = ST_IDLE
        self._material = None
        self._head_type = "8X"
        self._sn = ""
        self._readings = []
        self._runs = 0
        self._total = 0

    # ------------------------------------------------------------------ #
    #  Điều khiển từ giao diện (luồng GUI)                                #
    # ------------------------------------------------------------------ #
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        try:
            self.plc.close()
        except Exception:                    # noqa: BLE001
            pass

    def set_selection(self, material, head_type):
        """Đổi mã liệu / loại đầu (chỉ khi đang chờ, không khi đang chạy)."""
        with self._lock:
            if self._state == ST_RUNNING:
                running = True
            else:
                running = False
                self._material = material
                self._head_type = head_type
        if running:
            self._emit("log", text="Đang chạy — không đổi được lựa chọn.")

    def arm(self, material, head_type):
        self._drain_sn_queue()
        with self._lock:
            self._material = material
            self._head_type = head_type
            self._armed = True
            self._state = ST_WAIT_SCAN
            self._sn = ""
            self._readings = []
            self._runs = 0
        self._emit("state", state=ST_WAIT_SCAN)
        self._emit("status", text="Đã bật. Chờ quét mã (loại %s)." % head_type)

    def disarm(self):
        with self._lock:
            self._armed = False
            self._state = ST_IDLE
        self._emit("state", state=ST_IDLE)
        self._emit("status", text="Đã dừng.")

    def submit_sn(self, sn):
        sn = (sn or "").strip()
        if not sn:
            return
        with self._lock:
            ready = self._armed and self._state == ST_WAIT_SCAN
        if ready:
            self._sn_queue.put(sn)
        else:
            self._emit("log", text="Bỏ qua mã '%s' (chưa sẵn sàng quét)." % sn)

    def _drain_sn_queue(self):
        try:
            while True:
                self._sn_queue.get_nowait()
        except queue.Empty:
            pass

    def simulate_trigger(self):
        """Bấm nút giả lập tín hiệu PLC (chỉ có tác dụng ở chế độ Mock)."""
        if not isinstance(self.plc, MockPlcClient):
            return
        with self._lock:
            head_type = self._head_type
        side_cfg = getattr(self.cfg, self.side_key)
        trig, _ = side_addresses(side_cfg, head_type)
        self.plc.pulse(trig)

    # ------------------------------------------------------------------ #
    #  Vòng lặp nền                                                       #
    # ------------------------------------------------------------------ #
    def _run_loop(self):
        self._connect_plc()
        side_cfg = getattr(self.cfg, self.side_key)
        interval = max(0.02, self.cfg.poll_interval_ms / 1000.0)
        prev_trig = 1     # khởi tạo mức cao để chỉ bắt sườn lên 0->1

        while not self._stop.is_set():
            with self._lock:
                armed = self._armed
                state = self._state
                material = self._material
                head_type = self._head_type

            if not armed:
                prev_trig = 1
                time.sleep(interval)
                continue

            # --- Đang chờ quét SN ---
            if state == ST_WAIT_SCAN:
                sn = self._poll_sn()
                if sn is not None:
                    self._begin_sn(side_cfg, material, head_type, sn)
                    with self._lock:
                        if self._state == ST_RUNNING:
                            trig, _ = side_addresses(side_cfg, head_type)
                    if self._state == ST_RUNNING:
                        prev_trig = self._safe_read_bit(trig)
                        if prev_trig is None:
                            prev_trig = 1
                time.sleep(interval)
                continue

            # --- Đang chạy: poll trigger, bắt sườn lên ---
            trig, done = side_addresses(side_cfg, head_type)
            cur = self._safe_read_bit(trig)
            if cur is None:                  # lỗi PLC -> thử lại vòng sau
                time.sleep(interval)
                continue
            if prev_trig == 0 and cur == 1:
                self._handle_one_run(side_cfg, head_type, trig, done)
                nxt = self._safe_read_bit(trig)
                prev_trig = 0 if nxt is None else nxt
            else:
                prev_trig = cur
            time.sleep(interval)

    # ------------------------------------------------------------------ #
    #  Các bước                                                           #
    # ------------------------------------------------------------------ #
    def _begin_sn(self, side_cfg, material, head_type, sn):
        total = head_count(material, head_type)
        mat_name = material.name if material else "?"
        if total <= 0:
            self._emit("log", text="Mã liệu '%s' không có đầu %s — bỏ qua SN %s."
                       % (mat_name, head_type, sn))
            return
        with self._lock:
            self._sn = sn
            self._readings = []
            self._runs = 0
            self._total = total
            self._state = ST_RUNNING
        self._emit("state", state=ST_RUNNING)
        self._emit("sn", sn=sn)
        self._emit("progress", done=0, total=total)
        self._emit("status", text="SN %s — chờ tín hiệu PLC (0/%d đầu %s)"
                   % (sn, total, head_type))
        self._emit("log", text="── Bắt đầu SN %s | mã liệu %s | %d đầu %s ──"
                   % (sn, mat_name, total, head_type))

    def _handle_one_run(self, side_cfg, head_type, trig, done):
        with self._lock:
            idx = self._runs + 1
            total = self._total
        self._emit("log", text="Nhận tín hiệu chạy — đầu %d/%d" % (idx, total))

        # đọc dòng mới nhất của bên này
        try:
            reading = data_reader.get_latest_for_side(
                self.cfg.paths, side_cfg, head_type)
            self._emit("log", text="  Đọc %s: judge=%s, %d giá trị"
                       % (os.path.basename(reading["file"]),
                          reading["judge"], len(reading["values"])))
        except Exception as ex:              # noqa: BLE001
            reading = {"time": "", "judge": "NG", "values": [],
                       "headers": [], "raw": [], "file": ""}
            self._emit("log", text="  LỖI đọc file: %s — đầu này tính NG" % ex)

        with self._lock:
            self._readings.append(reading)
            self._runs += 1
            runs = self._runs
            total = self._total
            sn = self._sn
            readings = list(self._readings)
        self._emit("progress", done=runs, total=total)
        # gửi chi tiết đầu vừa đọc lên bảng dữ liệu
        self._emit("reading", sn=sn, head_type=head_type, index=idx, total=total,
                   judge=reading.get("judge", ""), time=reading.get("time", ""),
                   values=reading.get("values", []),
                   file=os.path.basename(reading.get("file", "") or ""))

        # bắt tay 'done' về PLC
        self._handshake_done(trig, done)

        if runs >= total:
            self._finish(sn, readings)

    def _handshake_done(self, trig, done):
        """Ghi done=1 báo hoàn thành; chờ PLC nhả trigger; hạ done=0."""
        self._safe_write_bit(done, 1)
        if self.cfg.simulation:
            self._safe_write_bit(trig, 0)    # PLC giả nhả tín hiệu
        else:
            t0 = time.time()
            while (time.time() - t0 < self.cfg.handshake_timeout_s
                   and not self._stop.is_set()):
                if self._safe_read_bit(trig) == 0:
                    break
                time.sleep(max(0.02, self.cfg.poll_interval_ms / 1000.0))
        self._safe_write_bit(done, 0)

    def _finish(self, sn, readings):
        payload = mes_api.build_payload(sn, readings, self.cfg.api.data_format)
        self._emit("log", text="Đủ %d đầu → POST MES: sn=%s, result=%s"
                   % (len(readings), payload["sn"], payload["result"]))
        ok, code, text = mes_api.post_payload(
            self.cfg.api.url, payload,
            timeout=self.cfg.api.timeout, retries=self.cfg.api.retries,
            verify_ssl=self.cfg.api.verify_ssl,
            logger=lambda m: self._emit("log", text="  " + m))
        if ok:
            self._emit("log", text="  [OK] MES nhận OK (HTTP %s)" % code)
        else:
            self._emit("log", text="  [FAIL] MES THẤT BẠI: %s" % text)
        self._emit("result", sn=sn, result=payload["result"], ok=ok)

        with self._lock:
            self._state = ST_WAIT_SCAN
            self._sn = ""
            self._readings = []
            self._runs = 0
        self._emit("state", state=ST_WAIT_SCAN)
        self._emit("status", text="Hoàn tất SN %s. Chờ quét mã tiếp theo." % sn)

    # ------------------------------------------------------------------ #
    #  Tiện ích PLC + hàng đợi SN                                         #
    # ------------------------------------------------------------------ #
    def _connect_plc(self):
        if self.cfg.simulation:
            try:
                self.plc.connect()
            except Exception:                # noqa: BLE001
                pass
            self._emit("plc", connected=True)
            self._emit("log", text="Chế độ GIẢ LẬP — không cần PLC/scan thật.")
            return
        try:
            self.plc.connect()
            self._emit("plc", connected=True)
            self._emit("log", text="PLC kết nối OK (%s:%s)."
                       % (getattr(self.plc, "ip", "?"),
                          getattr(self.plc, "port", "?")))
        except Exception as ex:              # noqa: BLE001
            self._emit("plc", connected=False)
            self._emit("log", text="Không kết nối được PLC: %s" % ex)

    def _safe_read_bit(self, device):
        try:
            v = self.plc.read_bit(device)
            return 1 if v else 0
        except Exception as ex:              # noqa: BLE001
            self._emit("plc", connected=False)
            self._emit("log", text="Lỗi đọc PLC %s: %s" % (device, ex))
            try:                              # thử kết nối lại
                self.plc.connect()
                self._emit("plc", connected=True)
            except Exception:                # noqa: BLE001
                pass
            return None

    def _safe_write_bit(self, device, value):
        try:
            self.plc.write_bit(device, value)
            return True
        except Exception as ex:              # noqa: BLE001
            self._emit("plc", connected=False)
            self._emit("log", text="Lỗi ghi PLC %s: %s" % (device, ex))
            return False

    def _poll_sn(self):
        try:
            return self._sn_queue.get_nowait()
        except queue.Empty:
            return None

    def _emit(self, event_type, **data):
        if self.on_event:
            try:
                self.on_event(event_type, **data)
            except Exception:                # noqa: BLE001
                pass
