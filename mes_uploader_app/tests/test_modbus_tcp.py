# -*- coding: utf-8 -*-
"""Modbus/TCP client: dựng đúng request + đọc/ghi phản hồi (socket giả, phân
mảnh). Không cần PLC thật.

Chạy:  python -m tests.test_modbus_tcp
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader.hardware.modbus_tcp import ModbusTcpClient, modbus_addr


class _FakeSock:
    """recv() trả tối đa 'chunk' byte/lần (mô phỏng TCP phân mảnh)."""

    def __init__(self, response, chunk=1):
        self._resp = response
        self._chunk = chunk
        self._pos = 0
        self.sent = b""

    def sendall(self, data):
        self.sent += data

    def recv(self, n):
        end = min(self._pos + min(n, self._chunk), len(self._resp))
        out = self._resp[self._pos:end]
        self._pos = end
        return out

    def close(self):
        pass


def _mbap(tid, pdu, unit=0xFF):
    return struct.pack(">HHHB", tid, 0, len(pdu) + 1, unit) + pdu


def main():
    # modbus_addr: lấy số từ 'D4200' / 'M100'
    assert modbus_addr("D4200") == 4200 and modbus_addr("M100") == 100
    assert modbus_addr("4200") == 4200

    # 1) Đọc Holding Register D4200 = 0x0007 (FC03)
    plc = ModbusTcpClient("1.2.3.4", 502, unit=0xFF)
    resp_pdu = struct.pack(">BB", 0x03, 2) + struct.pack(">H", 7)  # FC + bytecount + 1 word
    plc.sock = _FakeSock(_mbap(1, resp_pdu), chunk=1)
    assert plc.read_word("D4200") == 7
    sent = plc.sock.sent
    # MBAP(7) + PDU: FC03, addr=4200, qty=1
    assert sent[7] == 0x03 and struct.unpack(">H", sent[8:10])[0] == 4200
    assert struct.unpack(">H", sent[10:12])[0] == 1
    print("1) đọc Holding Register D4200 = 7 (FC03), request đúng ✔")

    # 2) Ghi Holding Register D4200 = 2 (FC06), phản hồi echo
    echo = struct.pack(">BHH", 0x06, 4200, 2)
    plc.sock = _FakeSock(_mbap(2, echo), chunk=3)
    assert plc.write_word("D4200", 2) is True
    sent = plc.sock.sent
    assert sent[7] == 0x06 and struct.unpack(">H", sent[8:10])[0] == 4200
    assert struct.unpack(">H", sent[10:12])[0] == 2
    print("2) ghi Holding Register D4200 = 2 (FC06) ✔")

    # 3) Đọc Coil M100 = 1 (FC01)
    resp_pdu = struct.pack(">BB", 0x01, 1) + bytes([0x01])  # FC + bytecount + coil byte (bit0=1)
    plc.sock = _FakeSock(_mbap(3, resp_pdu), chunk=1)
    assert plc.read_bit("M100") == 1
    assert plc.sock.sent[7] == 0x01
    print("3) đọc Coil M100 = 1 (FC01) ✔")

    # 4) Ghi Coil M100 = 1 (FC05 -> 0xFF00)
    echo = struct.pack(">BHH", 0x05, 100, 0xFF00)
    plc.sock = _FakeSock(_mbap(4, echo), chunk=2)
    assert plc.write_bit("M100", 1) is True
    sent = plc.sock.sent
    assert sent[7] == 0x05 and struct.unpack(">H", sent[10:12])[0] == 0xFF00
    print("4) ghi Coil M100 = 1 (FC05) ✔")

    # 5) Modbus exception -> báo lỗi rõ ràng
    exc = struct.pack(">BB", 0x83, 0x02)        # FC03|0x80, code 2 (illegal addr)
    plc.sock = _FakeSock(_mbap(5, exc), chunk=1)
    try:
        plc.read_word("D9999")
        assert False
    except IOError as ex:
        assert "exception" in str(ex)
    print("5) Modbus exception -> báo lỗi rõ ràng ✔")

    print("\nTEST MODBUS-TCP PASS ✔")


if __name__ == "__main__":
    main()
