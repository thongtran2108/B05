# -*- coding: utf-8 -*-
"""Modbus/TCP client (master) thuần socket — đọc/ghi PLC qua Modbus TCP.

Dùng khi PLC (vd FX5U) bật **Modbus/TCP server** thay vì SLMP. Ánh xạ thiết bị:
  - WORD (D…) -> Holding Register : đọc FC03, ghi FC06
  - BIT  (M…) -> Coil            : đọc FC01, ghi FC05
SỐ trong tên thiết bị = ĐỊA CHỈ Modbus (0-based). PLC phải map địa chỉ Modbus
này về đúng D/M (Modbus Device Assignment trên FX5U). Vd 'D4200' -> Holding
Register 4200; PLC cấu hình HR4200 ↔ D4200.

Giao diện TRÙNG PlcClient: connect / close / is_connected + read_word /
write_word / read_bit / write_bit; tự kết nối lại khi lỗi (drop socket hỏng).
Modbus dùng big-endian (network order).
"""

import socket
import struct
import threading


def modbus_addr(device):
    """Lấy ĐỊA CHỈ Modbus (số) từ tên thiết bị: 'D4200' -> 4200, '40' -> 40."""
    d = (device or "").strip().upper()
    i = 0
    while i < len(d) and not d[i].isdigit():
        i += 1
    return int(d[i:]) if d[i:] else 0


class ModbusTcpClient:
    """Modbus/TCP master, giữ socket bền + tự kết nối lại (như PlcClient)."""

    def __init__(self, ip, port=502, timeout=3.0, unit=0xFF):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.unit = unit & 0xFF
        self.sock = None
        self._tid = 0
        self._lock = threading.Lock()

    @property
    def is_connected(self):
        return self.sock is not None

    def connect(self):
        with self._lock:
            self._ensure_locked()
            return True

    def close(self):
        with self._lock:
            self._close_locked()

    # ------------------------------------------------------------------ #
    #  Giao diện trùng PlcClient                                          #
    # ------------------------------------------------------------------ #
    def read_word(self, device):
        return self._io(lambda: self._read_holding(modbus_addr(device), 1)[0])

    def write_word(self, device, value):
        return self._io(lambda: self._write_register(modbus_addr(device), value))

    def read_bit(self, device):
        return self._io(lambda: self._read_coils(modbus_addr(device), 1)[0])

    def write_bit(self, device, value):
        return self._io(lambda: self._write_coil(modbus_addr(device), value))

    # ------------------------------------------------------------------ #
    #  Kết nối + 1 giao dịch (tự bỏ socket hỏng khi lỗi)                  #
    # ------------------------------------------------------------------ #
    def _io(self, fn):
        with self._lock:
            self._ensure_locked()
            try:
                return fn()
            except Exception:                # noqa: BLE001
                self._close_locked()         # bỏ socket hỏng -> lần sau nối lại
                raise

    def _ensure_locked(self):
        if self.sock is None:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.connect((self.ip, self.port))
            self.sock = s

    def _close_locked(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:                # noqa: BLE001
                pass
            self.sock = None

    def _recv_exact(self, n):
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise IOError("Modbus: PLC dong ket noi (nhan %d/%d byte)"
                              % (len(buf), n))
            buf += chunk
        return bytes(buf)

    def _txn(self, pdu):
        """Gửi 1 PDU (đã có function code), trả về PDU phản hồi."""
        self._tid = (self._tid + 1) & 0xFFFF
        # MBAP: transaction id, protocol id (0), length, unit id
        mbap = struct.pack(">HHHB", self._tid, 0, len(pdu) + 1, self.unit)
        self.sock.sendall(mbap + pdu)

        head = self._recv_exact(7)           # MBAP phản hồi
        _tid, _proto, length, _unit = struct.unpack(">HHHB", head)
        if length < 1:
            raise IOError("Modbus: do dai phan hoi sai (%d)" % length)
        resp = self._recv_exact(length - 1)  # PDU phản hồi
        fc = resp[0]
        if fc & 0x80:                        # mã lỗi (exception)
            code = resp[1] if len(resp) > 1 else 0
            raise IOError("Modbus exception FC=0x%02X, code=%d" % (fc & 0x7F, code))
        return resp

    # ------------------------------------------------------------------ #
    #  Hàm Modbus cơ bản                                                  #
    # ------------------------------------------------------------------ #
    def _read_holding(self, addr, count):    # FC03
        resp = self._txn(struct.pack(">BHH", 0x03, addr, count))
        bc = resp[1] if len(resp) > 1 else 0
        data = resp[2:2 + bc]
        if len(data) < count * 2:
            raise IOError("Modbus: thieu du lieu HR (%d/%d byte)"
                          % (len(data), count * 2))
        return [struct.unpack(">H", data[i:i + 2])[0]
                for i in range(0, count * 2, 2)]

    def _write_register(self, addr, value):  # FC06
        self._txn(struct.pack(">BHH", 0x06, addr, value & 0xFFFF))
        return True

    def _read_coils(self, addr, count):      # FC01
        resp = self._txn(struct.pack(">BHH", 0x01, addr, count))
        bc = resp[1] if len(resp) > 1 else 0
        bits = []
        for byte in resp[2:2 + bc]:
            for b in range(8):
                bits.append((byte >> b) & 1)
        if len(bits) < count:
            raise IOError("Modbus: thieu coil (%d/%d)" % (len(bits), count))
        return bits[:count]

    def _write_coil(self, addr, value):      # FC05
        self._txn(struct.pack(">BHH", 0x05, addr, 0xFF00 if value else 0x0000))
        return True
