# -*- coding: utf-8 -*-
"""Khung phản hồi PLC bị PHÂN MẢNH TCP vẫn đọc đủ (sửa lỗi
'unpack requires a buffer of 2 bytes' khi đọc D... trên FX5U thật).

Chạy:  python -m tests.test_plc_frame
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader.hardware.mitsubishi_plc import MitsubishiPLC


class _FakeSock:
    """Socket giả: recv() trả về TỐI ĐA 'chunk' byte mỗi lần (mô phỏng TCP
    phân mảnh) để tái hiện lỗi nhận thiếu của bản cũ (1 recv duy nhất)."""

    def __init__(self, response, chunk=1):
        self._resp = response
        self._chunk = chunk
        self._pos = 0
        self.sent = b""

    def sendall(self, data):
        self.sent += data

    def send(self, data):
        self.sent += data
        return len(data)

    def recv(self, n):
        end = min(self._pos + min(n, self._chunk), len(self._resp))
        out = self._resp[self._pos:end]
        self._pos = end
        return out

    def close(self):
        pass


def _resp_words(words):
    """Dựng khung phản hồi 3E binary cho lệnh đọc word."""
    data = b"".join(struct.pack('<H', w) for w in words)
    resp_len = 2 + len(data)             # end_code(2) + data
    return (b'\xD0\x00\x00\xFF\xFF\x03\x00' + struct.pack('<H', resp_len)
            + b'\x00\x00' + data)


def _resp_bits(bits):
    """Dựng khung phản hồi 3E binary cho lệnh đọc bit (2 bit/byte)."""
    data = bytearray()
    for i in range(0, len(bits), 2):
        hi = 0x10 if bits[i] else 0x00
        lo = 0x01 if (i + 1 < len(bits) and bits[i + 1]) else 0x00
        data.append(hi | lo)
    resp_len = 2 + len(data)
    return (b'\xD0\x00\x00\xFF\xFF\x03\x00' + struct.pack('<H', resp_len)
            + b'\x00\x00' + bytes(data))


def main():
    # 1) Đọc 1 word, phản hồi bị cắt 1 byte/lần (phân mảnh tối đa)
    plc = MitsubishiPLC("1.2.3.4", 5000)
    plc.sock = _FakeSock(_resp_words([1]), chunk=1)
    assert plc.read_word("D4206") == 1
    print("1) đọc 1 word (D4206) qua phản hồi phân mảnh -> OK")

    # 2) Đọc nhiều word, phân mảnh 3 byte/lần
    plc.sock = _FakeSock(_resp_words([7, 8, 9]), chunk=3)
    assert plc.read_words("D100", 3) == [7, 8, 9]
    print("2) đọc nhiều word -> OK")

    # 3) Ghi word: phản hồi chỉ có end_code (2 byte), cũng phân mảnh
    write_resp = b'\xD0\x00\x00\xFF\xFF\x03\x00' + struct.pack('<H', 2) + b'\x00\x00'
    plc.sock = _FakeSock(write_resp, chunk=1)
    assert plc.write_word("D4200", 1) is True
    print("3) ghi word (D4200) -> OK")

    # 4) PLC trả end_code lỗi -> ném IOError rõ ràng (không phải unpack)
    err_resp = b'\xD0\x00\x00\xFF\xFF\x03\x00' + struct.pack('<H', 2) + b'\x51\xC0'
    plc.sock = _FakeSock(err_resp, chunk=2)
    try:
        plc.read_word("D4206")
        assert False, "phải ném lỗi end_code"
    except IOError as ex:
        assert "end code" in str(ex)
    print("4) end_code != 0 -> báo lỗi rõ ràng")

    # 5) Đọc BIT (M...) qua phản hồi phân mảnh
    plc.sock = _FakeSock(_resp_bits([1]), chunk=1)
    assert plc.read_bit("M100") == 1
    plc.sock = _FakeSock(_resp_bits([0]), chunk=1)
    assert plc.read_bit("M100") == 0
    print("5) đọc bit (M100) qua phản hồi phân mảnh -> OK")

    print("\nTEST PLC-FRAME PASS ✔")


if __name__ == "__main__":
    main()
