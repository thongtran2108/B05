# -*- coding: utf-8 -*-
"""Kiểm thử 3 chế độ chạy: 'sim' (giả lập) / 'manual_sn' (PLC thật + SN tay) /
'live' (thật) — qua app_mode() và manual_sn_entry().

Chạy:  python -m tests.test_mode
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader.config import (AppConfig, app_mode, manual_sn_entry,
                                 _from_dict)


def main():
    c = AppConfig()

    # 1) Giả lập: PLC Mock + nhập SN tay
    c.simulation = True; c.manual_sn = False
    assert app_mode(c) == "sim"
    assert manual_sn_entry(c) is True       # SN nhập tay
    print("1) sim -> manual SN ✔")

    # 2) PLC thật + nhập SN tay (KHÔNG cần tay scan)
    c.simulation = False; c.manual_sn = True
    assert app_mode(c) == "manual_sn"
    assert manual_sn_entry(c) is True       # vẫn nhập SN tay (không mở COM)
    print("2) manual_sn -> PLC thật + SN tay ✔")

    # 3) Thật: PLC thật + tay scan COM
    c.simulation = False; c.manual_sn = False
    assert app_mode(c) == "live"
    assert manual_sn_entry(c) is False      # SN từ tay scan
    print("3) live -> PLC thật + tay scan ✔")

    # 4) Cấu hình cũ (thiếu manual_sn) -> mặc định 'live' khi simulation=False
    old = _from_dict(AppConfig, {"simulation": False})
    assert app_mode(old) == "live" and manual_sn_entry(old) is False
    print("4) cấu hình cũ thiếu manual_sn -> live ✔")

    print("\nTEST MODE PASS ✔")


if __name__ == "__main__":
    main()
