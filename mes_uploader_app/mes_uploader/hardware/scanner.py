# -*- coding: utf-8 -*-
"""Đọc mã từ tay scan dạng cổng COM (pyserial).

Tay scan kiểu "keyboard wedge qua COM" thường gửi chuỗi mã kết thúc bằng
CR/LF. SerialScanner chạy trên 1 luồng riêng, đọc từng dòng và gọi callback
on_scan(sn) mỗi khi quét được 1 mã.

Tay trái -> dùng cho bên trái, tay phải -> bên phải (mỗi tay 1 cổng COM).
Ở chế độ giả lập (simulation) thì KHÔNG mở cổng COM; giao diện sẽ tự gọi
on_scan(sn) khi bấm nút "Quét (giả lập)".
"""

import threading

try:
    import serial            # pyserial
except ImportError:
    serial = None


class SerialScanner:
    """Đọc mã liên tục từ 1 cổng COM trên luồng nền."""

    def __init__(self, port, baud=9600, on_scan=None, on_error=None):
        self.port = port
        self.baud = baud
        self.on_scan = on_scan
        self.on_error = on_error
        self._ser = None
        self._thread = None
        self._stop = threading.Event()

    def start(self):
        if serial is None:
            if self.on_error:
                self.on_error("Chua cai 'pyserial' (pip install pyserial)")
            return False
        try:
            self._ser = serial.Serial(self.port, self.baud, timeout=0.3)
        except Exception as ex:          # noqa: BLE001
            if self.on_error:
                self.on_error("Khong mo duoc cong %s: %s" % (self.port, ex))
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def _loop(self):
        buf = bytearray()
        while not self._stop.is_set():
            try:
                chunk = self._ser.read(64)
            except Exception as ex:      # noqa: BLE001
                if self.on_error:
                    self.on_error("Loi doc scan %s: %s" % (self.port, ex))
                break
            if not chunk:
                continue
            buf.extend(chunk)
            # tách theo CR / LF
            while b"\n" in buf or b"\r" in buf:
                idx = min((buf.index(b) for b in (b"\n", b"\r") if b in buf))
                line = bytes(buf[:idx]).strip()
                del buf[:idx + 1]
                if line and self.on_scan:
                    try:
                        self.on_scan(line.decode("utf-8", "ignore").strip())
                    except Exception:    # noqa: BLE001
                        pass

    def stop(self):
        self._stop.set()
        if self._ser:
            try:
                self._ser.close()
            except Exception:            # noqa: BLE001
                pass
            self._ser = None
