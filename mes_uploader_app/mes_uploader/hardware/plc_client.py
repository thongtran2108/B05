# -*- coding: utf-8 -*-
"""Wrapper quản lý kết nối PLC + bản Mock để chạy giả lập (không cần PLC).

Giao diện chung (dùng trong máy trạng thái):
    connect()            -> mở kết nối (Mock luôn 'kết nối')
    close()
    is_connected         -> bool
    read_bit(device)     -> 0/1
    write_bit(device, v)
"""

import threading

from .mitsubishi_plc import MitsubishiPLC, is_word_device


class PlcClient:
    """Kết nối thật tới PLC Mitsubishi, giữ socket bền và tự kết nối lại."""

    def __init__(self, ip, port=5000, timeout=3.0):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self._plc = None
        self._lock = threading.Lock()

    @property
    def is_connected(self):
        return self._plc is not None and self._plc.sock is not None

    def connect(self):
        with self._lock:
            if self.is_connected:
                return True
            self._plc = MitsubishiPLC(self.ip, self.port, self.timeout)
            self._plc.connect()
            return True

    def close(self):
        with self._lock:
            if self._plc:
                try:
                    self._plc.close()
                except Exception:        # noqa: BLE001
                    pass
                self._plc = None

    def _ensure(self):
        if not self.is_connected:
            self.connect()

    def read_bit(self, device):
        with self._lock:
            self._ensure_locked()
            return self._plc.read_bit(device)

    def write_bit(self, device, value):
        with self._lock:
            self._ensure_locked()
            return self._plc.write_bit(device, value)

    def read_word(self, device):
        with self._lock:
            self._ensure_locked()
            return self._plc.read_word(device)

    def write_word(self, device, value):
        with self._lock:
            self._ensure_locked()
            return self._plc.write_word(device, value)

    def _ensure_locked(self):
        if not (self._plc is not None and self._plc.sock is not None):
            self._plc = MitsubishiPLC(self.ip, self.port, self.timeout)
            self._plc.connect()


class MockPlcClient:
    """Giả lập PLC bằng dict bit trong bộ nhớ — phục vụ chạy thử giao diện.

    - read_bit / write_bit thao tác trên dict.
    - pulse(device): mô phỏng PLC bật bit trigger lên 1 (bấm nút trên UI).
    """

    def __init__(self, *args, **kwargs):
        self._bits = {}
        self._words = {}
        self._lock = threading.Lock()
        self._connected = False

    @property
    def is_connected(self):
        return self._connected

    def connect(self):
        self._connected = True
        return True

    def close(self):
        self._connected = False

    def read_bit(self, device):
        with self._lock:
            return self._bits.get(device.upper(), 0)

    def write_bit(self, device, value):
        with self._lock:
            self._bits[device.upper()] = 1 if value else 0
        return True

    def read_word(self, device):
        with self._lock:
            return self._words.get(device.upper(), 0)

    def write_word(self, device, value):
        with self._lock:
            self._words[device.upper()] = int(value) & 0xFFFF
        return True

    # --- dành cho nút "giả lập tín hiệu PLC" trên giao diện ---
    def pulse(self, device):
        """PLC giả bật trigger lên 1 (bit hoặc thanh ghi word, báo 1 lần chạy)."""
        with self._lock:
            if is_word_device(device):
                self._words[device.upper()] = 1
            else:
                self._bits[device.upper()] = 1


def make_plc_client(cfg, side_cfg):
    """Tạo client phù hợp: Mock nếu simulation, ngược lại PLC thật.

    Ưu tiên IP/port riêng của bên (plc_ip/plc_port); nếu trống dùng PLC chung.
    """
    if cfg.simulation:
        return MockPlcClient()
    ip = side_cfg.plc_ip or cfg.plc.ip
    port = side_cfg.plc_port or cfg.plc.port
    return PlcClient(ip, port, cfg.plc.timeout)
