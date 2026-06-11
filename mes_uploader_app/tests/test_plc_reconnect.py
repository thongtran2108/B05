# -*- coding: utf-8 -*-
"""PlcClient TỰ PHỤC HỒI khi chạy dài: thao tác lỗi (mạng/PLC chớp tắt) ->
bỏ socket hỏng -> lần gọi sau tự kết nối lại.

Chạy:  python -m tests.test_plc_reconnect
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader.hardware import plc_client


class _FakePLC:
    """Giả MitsubishiPLC: bản đầu tiên gây lỗi đọc, các bản sau đọc OK."""
    instances = 0

    def __init__(self, ip, port=5000, timeout=3.0, ascii_mode=False):
        _FakePLC.instances += 1
        self._fail = (_FakePLC.instances == 1)   # chỉ bản đầu lỗi
        self.sock = object()                     # coi như đã kết nối

    def connect(self):
        self.sock = object()
        return self

    def close(self):
        self.sock = None

    def read_word(self, device):
        if self._fail:
            raise IOError("rớt mạng giả lập")
        return 7


def main():
    plc_client.MitsubishiPLC = _FakePLC          # monkeypatch
    _FakePLC.instances = 0
    c = plc_client.PlcClient("1.2.3.4", 5000)

    # 1) Lần đầu: lỗi -> ném ngoại lệ + BỎ socket hỏng
    try:
        c.read_word("D0")
        assert False, "phải ném lỗi ở lần đầu"
    except IOError:
        pass
    assert c._plc is None, "socket hỏng phải được bỏ để lần sau kết nối lại"
    print("1) thao tác lỗi -> bỏ socket hỏng ✔")

    # 2) Lần sau: tự tạo kết nối MỚI (bản #2, không lỗi) -> đọc OK
    assert c.read_word("D0") == 7, "lần sau phải đọc được sau khi kết nối lại"
    assert _FakePLC.instances == 2, "phải tạo kết nối mới sau lỗi (không kẹt)"
    print("2) lần gọi sau tự kết nối lại, đọc OK ✔")

    print("\nTEST PLC-RECONNECT PASS ✔")


if __name__ == "__main__":
    main()
