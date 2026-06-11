# -*- coding: utf-8 -*-
"""Khung 3E ASCII cho PLC để Communication Data Code = ASCII.

Kiểm tra: app dựng đúng request ASCII và đọc/ghi được phản hồi ASCII (qua
socket giả, có phân mảnh). Không cần PLC thật.

Chạy:  python -m tests.test_plc_ascii
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader.hardware.mitsubishi_plc import MitsubishiPLC


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


def _ascii_resp(end_code, data_str):
    """Dựng khung phản hồi 3E ASCII: header + len + end_code(4) + data."""
    body = ("%04X" % end_code) + data_str
    head = "D00000FF03FF00" + ("%04X" % len(body))   # 14 + 4 = 18 ký tự
    return (head + body).encode("ascii")


def main():
    plc = MitsubishiPLC("1.2.3.4", 5000, ascii_mode=True)

    # 1) Đọc 1 word D4206 = 0x0001, phản hồi phân mảnh 1 byte/lần
    plc.sock = _FakeSock(_ascii_resp(0, "0001"), chunk=1)
    assert plc.read_word("D4206") == 1
    sent = plc.sock.sent.decode("ascii")
    print(" req:", sent)
    # request ASCII đúng: 3E + Read(0401) + word(0000) + D*004206 + 1 điểm(0001)
    assert sent.startswith("5000") and "0401" in sent
    assert "D*004206" in sent and sent.endswith("0001")
    print("1) đọc word D4206 (ASCII) = 1, request đúng định dạng ✔")

    # 2) Đọc nhiều word
    plc.sock = _FakeSock(_ascii_resp(0, "0007000800FF"), chunk=5)
    assert plc.read_words("D100", 3) == [7, 8, 255]
    print("2) đọc nhiều word (ASCII) ✔")

    # 3) Ghi word D4200 = 2
    plc.sock = _FakeSock(_ascii_resp(0, ""), chunk=2)
    assert plc.write_word("D4200", 2) is True
    sent = plc.sock.sent.decode("ascii")
    assert "1401" in sent and "D*004200" in sent and sent.endswith("0001" "0002")
    print("3) ghi word D4200=2 (ASCII), request đúng ✔")

    # 4) Đọc bit M100 (ASCII: mỗi bit 1 ký tự)
    plc.sock = _FakeSock(_ascii_resp(0, "1"), chunk=1)
    assert plc.read_bit("M100") == 1
    sent = plc.sock.sent.decode("ascii")
    assert "M*000100" in sent
    print("4) đọc bit M100 (ASCII) = 1 ✔")

    # 5) end_code != 0 -> báo lỗi rõ ràng
    plc.sock = _FakeSock(_ascii_resp(0xC051, ""), chunk=3)
    try:
        plc.read_word("D0")
        assert False
    except IOError as ex:
        assert "end code" in str(ex)
    print("5) end_code != 0 (ASCII) -> báo lỗi rõ ràng ✔")

    print("\nTEST PLC-ASCII PASS ✔")


if __name__ == "__main__":
    main()
