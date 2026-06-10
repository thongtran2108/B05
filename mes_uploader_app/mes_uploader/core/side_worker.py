# -*- coding: utf-8 -*-
"""Máy trạng thái lưu trình cho 1 bên (Trái / Phải) — chạy trên luồng riêng.

Lưu trình (giống nhau cho cả 2 bên, nhưng độc lập):

  1. Người dùng chọn mã liệu + loại đầu (8X / 16X) rồi bấm "Bắt đầu" (arm).
  2. Quét SN bằng tay scan của bên đó  -> submit_sn(sn).
  2b. KIỂM TRA SN bằng GET (nếu bật): body phải BẰNG ĐÚNG chuỗi cho phép thì
      mới chạy; nếu không -> CHẶN, báo lỗi, chờ quét mã khác. Kết quả kiểm tra
      được ghi về PLC: OK = 1, NG = 2 (nếu có cấu hình thanh ghi).
  3. Số lần chạy = số đầu của loại đã chọn (vd ABC có 2 đầu 8X -> 2 lần).
  4. Mỗi lần PLC bật bit trigger (sườn lên 0->1):
        - đọc DÒNG MỚI NHẤT trong file của bên (CCD1 trái / CCD2 phải)
        - ghi bit 'done' = 1 báo hoàn thành về PLC; RESET tín hiệu trigger đã
          nhận về 0; hạ done = 0
  5. Khi đủ số đầu -> GỘP dữ liệu -> POST 1 lần lên MES (chỉ thành công khi
     body chứa chuỗi mong đợi) -> quay lại chờ quét.

Trong suốt bước 2b → 5, mọi mã quét mới đều bị bỏ qua: CHỈ sau khi POST xong
(quay về WAIT_SCAN) mới nhận SN tiếp theo.

Module này KHÔNG phụ thuộc PySide6: phát sự kiện qua callback on_event(type,
**data). Lớp giao diện sẽ marshal các sự kiện này về luồng GUI bằng signal.
"""

import datetime
import os
import queue
import threading
import time

from .. import data_reader, image_uploader, mes_api
from ..config import side_addresses, head_count, head_api, head_image
from ..hardware.plc_client import MockPlcClient
from ..i18n import tr


# Các trạng thái
ST_IDLE = "IDLE"            # chưa bật (chưa arm)
ST_WAIT_SCAN = "WAIT_SCAN"  # đã bật, đang chờ quét SN
ST_RUNNING = "RUNNING"      # đã có SN, đang chờ/tiếp nhận tín hiệu chạy

# Giá trị ghi về PLC cho kết quả kiểm tra SN (theo yêu cầu: OK=1, NG=2)
SN_RESULT_OK = 1
SN_RESULT_NG = 2


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
        self._img_queue = queue.Queue(maxsize=64)   # hàng đợi tải ảnh (nền)
        self._img_thread = None

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
        if self._img_thread:
            # chờ ảnh đang tải xong (có giới hạn); nếu đích treo, luồng nền
            # daemon sẽ tự kết thúc cùng tiến trình, không chặn việc dừng.
            self._img_thread.join(timeout=2.0)
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
            self._emit("log", text=tr("Đang chạy — không đổi được lựa chọn."))

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
        self._emit("status", text=tr("Đã bật. Chờ quét mã (loại %s).") % head_type)

    def disarm(self):
        with self._lock:
            self._armed = False
            self._state = ST_IDLE
        self._emit("state", state=ST_IDLE)
        self._emit("status", text=tr("Đã dừng."))

    def submit_sn(self, sn):
        sn = (sn or "").strip()
        if not sn:
            return
        with self._lock:
            ready = self._armed and self._state == ST_WAIT_SCAN
        if ready:
            self._sn_queue.put(sn)
        else:
            self._emit("log", text=tr("Bỏ qua mã '%s' (chưa sẵn sàng quét).") % sn)

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
            self._emit("log", text=tr("Mã liệu '%s' không có đầu %s — bỏ qua SN %s.")
                       % (mat_name, head_type, sn))
            return

        # --- Bước 2b: kiểm tra SN bằng GET trước khi cho chạy (theo API loại đầu) ---
        sn_ok = self._check_sn(sn, head_type)
        # ghi kết quả kiểm tra SN về PLC: OK = 1, NG = 2 (nếu có cấu hình thanh ghi)
        self._write_sn_result(side_cfg, sn_ok)
        if not sn_ok:
            return        # SN không hợp lệ -> ở lại WAIT_SCAN, chờ quét mã khác

        with self._lock:
            self._sn = sn
            self._readings = []
            self._runs = 0
            self._total = total
            self._state = ST_RUNNING
        self._emit("state", state=ST_RUNNING)
        self._emit("sn", sn=sn)
        self._emit("progress", done=0, total=total)
        self._emit("status", text=tr("SN %s — chờ tín hiệu PLC (0/%d đầu %s)")
                   % (sn, total, head_type))
        self._emit("log", text=tr("── Bắt đầu SN %s | mã liệu %s | %d đầu %s ──")
                   % (sn, mat_name, total, head_type))

    def _check_sn(self, sn, head_type):
        """GET kiểm tra SN theo API của loại đầu. True=hợp lệ (chạy), False=chặn."""
        api = self.cfg.api
        head = head_api(api, head_type)
        if not head.check_enabled:
            return True
        if not (head.check_url_prefix or head.check_url_suffix):
            self._emit("log", text=tr("  (Bỏ qua kiểm tra SN: chưa cấu hình URL GET cho đầu %s)")
                       % head_type)
            return True
        self._emit("log", text=tr("Kiểm tra SN %s qua GET (API đầu %s)…") % (sn, head_type))
        ok, msg = mes_api.check_sn(
            sn, head.check_url_prefix, head.check_url_suffix,
            ok_value=head.check_ok_value, timeout=api.timeout,
            verify_ssl=api.verify_ssl, use_proxy=api.use_proxy, proxy=api.proxy,
            logger=lambda m: self._emit("log", text="  " + m))
        if ok:
            self._emit("log", text=tr("  SN hợp lệ — cho phép chạy."))
            return True
        self._emit("log", text=tr("  [CHẶN] SN %s không hợp lệ: %s") % (sn, msg))
        self._emit("log", text=tr("  → Vui lòng quét mã khác."))
        self._emit("sn_rejected", sn=sn, message=msg)
        self._emit("status", text=tr("SN %s bị chặn: %s") % (sn, msg))
        return False

    def _handle_one_run(self, side_cfg, head_type, trig, done):
        with self._lock:
            idx = self._runs + 1
            total = self._total
        self._emit("log", text=tr("Nhận tín hiệu chạy — đầu %d/%d") % (idx, total))

        # đọc dòng mới nhất của bên này (CHỈ ngày hôm nay nếu require_today)
        try:
            reading = data_reader.get_latest_for_side(
                self.cfg.paths, side_cfg, head_type,
                require_today=self.cfg.paths.require_today)
            self._emit("log", text=tr("  Đọc %s: judge=%s, %d giá trị")
                       % (os.path.basename(reading["file"]),
                          reading["judge"], len(reading["values"])))
        except Exception as ex:              # noqa: BLE001
            # Thiếu dữ liệu ngày hôm nay / lỗi đọc -> BÁO LỖI và HỦY SN này
            # (không upload nhầm, không tính NG giả).
            self._abort_sn(trig, done, sn=self._sn, head_type=head_type,
                           index=idx, total=total, message=str(ex))
            return

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

        # tải ảnh AOI (OK/NG) lên link đích — xếp hàng, xử lý ở luồng nền
        self._enqueue_image_upload(sn, head_type, reading.get("judge", ""))

        # bắt tay 'done' về PLC
        self._handshake_done(trig, done)

        if runs >= total:
            self._finish(sn, readings, head_type)

    def _abort_sn(self, trig, done, sn, head_type, index, total, message):
        """Hủy SN đang chạy do thiếu dữ liệu: báo lỗi, KHÔNG upload, chờ quét lại.

        Vẫn nhả handshake với PLC để dây chuyền không bị treo; thao tác viên
        thấy lỗi trên giao diện và xử lý (vd file ngày hôm nay chưa được xuất).
        """
        self._emit("log", text=tr("  [LỖI] %s") % message)
        self._emit("log", text=tr("  → Hủy SN %s, KHÔNG tải lên MES. Vui lòng kiểm tra dữ liệu.")
                   % sn)
        self._emit("error", sn=sn, head_type=head_type, index=index,
                   total=total, message=message)

        # nhả handshake để PLC tiếp tục
        self._handshake_done(trig, done)

        with self._lock:
            self._state = ST_WAIT_SCAN
            self._sn = ""
            self._readings = []
            self._runs = 0
        self._emit("state", state=ST_WAIT_SCAN)
        self._emit("status", text=tr("LỖI thiếu dữ liệu — đã hủy SN %s. Chờ quét mã tiếp theo.")
                   % sn)

    def _enqueue_image_upload(self, sn, head_type, judge):
        """Xếp yêu cầu tải ảnh vào HÀNG ĐỢI để 1 luồng nền xử lý TUẦN TỰ.

        Tuần tự hóa giúp: không sinh vô số luồng khi đích (share) chậm/chết, và
        2 đầu cùng SN không ghi đè tên file của nhau. Bỏ qua im lặng nếu tắt
        tính năng ảnh hoặc loại đầu chưa cấu hình đường dẫn (nguồn/đích). Hàng
        đợi đầy (đích quá chậm) -> bỏ ảnh + ghi nhật ký, KHÔNG chặn dây chuyền.
        'when' + require_today chốt theo thời điểm nhận tín hiệu (copy diễn ra
        sau ở luồng nền).
        """
        images = getattr(self.cfg, "images", None)
        if not images or not images.enabled:
            return
        head_img = head_image(images, head_type)
        if not head_img.source_dir or not head_img.upload_dir:
            return
        job = (head_img, images, sn, judge, datetime.datetime.now(),
               self.cfg.paths.require_today)
        try:
            self._img_queue.put_nowait(job)
        except queue.Full:
            self._emit("log", text=tr("  [ẢNH] Bỏ qua: hàng đợi tải ảnh đầy (đích chậm?)"))
            return
        if self._img_thread is None or not self._img_thread.is_alive():
            self._img_thread = threading.Thread(target=self._image_loop,
                                                daemon=True)
            self._img_thread.start()

    def _image_loop(self):
        """Luồng nền DUY NHẤT: tải ảnh tuần tự theo hàng đợi tới khi dừng."""
        while not self._stop.is_set():
            try:
                job = self._img_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            self._do_image_upload(*job)

    def _do_image_upload(self, head_img, images, sn, judge, when, require_today):
        try:
            ok, msg, _dest = image_uploader.upload_latest_image(
                head_img.source_dir, head_img.upload_dir, sn, judge, when=when,
                sub_image=images.sub_image, ok_dir=images.ok_dir,
                ng_dir=images.ng_dir, extensions=images.extensions,
                require_today=require_today)
        except Exception as ex:              # noqa: BLE001 (luồng nền: không được chết)
            self._emit("log", text=tr("  [ẢNH] Bỏ qua: %s") % ex)
            return
        if ok:
            self._emit("log", text=tr("  [ẢNH] %s") % msg)
        else:
            self._emit("log", text=tr("  [ẢNH] Bỏ qua: %s") % msg)

    def _write_sn_result(self, side_cfg, ok):
        """Ghi kết quả kiểm tra SN về PLC: OK -> 1, NG -> 2.

        Chỉ ghi khi bên này có cấu hình thanh ghi (side_cfg.sn_result_reg).
        """
        reg = (getattr(side_cfg, "sn_result_reg", "") or "").strip()
        if not reg:
            return
        value = SN_RESULT_OK if ok else SN_RESULT_NG
        if self._safe_write_word(reg, value):
            self._emit("log", text=tr("  Ghi kết quả SN về PLC %s = %d") % (reg, value))

    def _handshake_done(self, trig, done):
        """Báo done về PLC rồi RESET tín hiệu trigger đã nhận về 0.

        Theo yêu cầu: tín hiệu nhận từ PLC, sau khi nhận xong, app GHI LẠI = 0
        (PLC pulse trigger rồi chờ app reset). Vẫn ghi bit 'done' để tương thích
        PLC nào dùng bắt tay 2 bit.
        """
        self._safe_write_bit(done, 1)
        self._safe_write_bit(trig, 0)        # reset tín hiệu trigger đã nhận về 0
        self._safe_write_bit(done, 0)

    def _finish(self, sn, readings, head_type):
        api = self.cfg.api
        head = head_api(api, head_type)
        result = mes_api.overall_result(readings)
        payload = mes_api.build_payload(
            sn, readings, station_name=head.station_name, emp_no=api.emp_no)
        self._emit("log", text=tr("Đủ %d đầu → POST MES (API đầu %s): sn=%s, result=%s")
                   % (len(readings), head_type, payload["sn"], result))
        ok, code, text = mes_api.post_payload(
            head.url, payload,
            timeout=api.timeout, retries=api.retries,
            verify_ssl=api.verify_ssl,
            use_proxy=api.use_proxy, proxy=api.proxy,
            ok_contains=head.post_ok_contains,
            logger=lambda m: self._emit("log", text="  " + m))
        if ok:
            self._emit("log", text=tr("  [OK] MES nhận OK (HTTP %s)") % code)
        else:
            self._emit("log", text=tr("  [FAIL] MES THẤT BẠI: %s")
                       % mes_api.short_error(code, text))
        self._emit("result", sn=sn, result=result, ok=ok)

        with self._lock:
            self._state = ST_WAIT_SCAN
            self._sn = ""
            self._readings = []
            self._runs = 0
        self._emit("state", state=ST_WAIT_SCAN)
        self._emit("status", text=tr("Hoàn tất SN %s. Chờ quét mã tiếp theo.") % sn)

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
            self._emit("log", text=tr("Chế độ GIẢ LẬP — không cần PLC/scan thật."))
            return
        try:
            self.plc.connect()
            self._emit("plc", connected=True)
            self._emit("log", text=tr("PLC kết nối OK (%s:%s).")
                       % (getattr(self.plc, "ip", "?"),
                          getattr(self.plc, "port", "?")))
        except Exception as ex:              # noqa: BLE001
            self._emit("plc", connected=False)
            self._emit("log", text=tr("Không kết nối được PLC: %s") % ex)

    def _safe_read_bit(self, device):
        try:
            v = self.plc.read_bit(device)
            return 1 if v else 0
        except Exception as ex:              # noqa: BLE001
            self._emit("plc", connected=False)
            self._emit("log", text=tr("Lỗi đọc PLC %s: %s") % (device, ex))
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
            self._emit("log", text=tr("Lỗi ghi PLC %s: %s") % (device, ex))
            return False

    def _safe_write_word(self, device, value):
        try:
            self.plc.write_word(device, value)
            return True
        except Exception as ex:              # noqa: BLE001
            self._emit("plc", connected=False)
            self._emit("log", text=tr("Lỗi ghi PLC %s: %s") % (device, ex))
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
