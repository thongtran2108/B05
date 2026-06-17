# -*- coding: utf-8 -*-
"""Kiểm thử ScanRouter — luân phiên 1 máy quét chung Trái <-> Phải.

Quy tắc: bắt đầu bên TRÁI; SN hợp lệ (OK) -> chuyển lượt sang bên kia; SN không
hợp lệ (NG) -> giữ lượt (quét lại bên đó).

Chạy:  python -m tests.test_scan_router
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader.core.scan_router import ScanRouter


def main():
    r = ScanRouter("left")
    assert r.route() == "left"                      # bắt đầu: bên TRÁI

    # đầu trái OK -> chuyển sang phải
    assert r.on_result("left", True) == "right"
    assert r.route() == "right"

    # phải OK -> quay lại trái
    assert r.on_result("right", True) == "left"
    assert r.route() == "left"

    # trái NG -> GIỮ lượt (quét lại trái)
    assert r.on_result("left", False) == "left"
    assert r.route() == "left"

    # sự kiện của bên KHÔNG phải lượt hiện tại -> bỏ qua (không đổi)
    assert r.on_result("right", True) == "left"
    assert r.route() == "left"

    # trái OK lần nữa -> sang phải
    assert r.on_result("left", True) == "right"

    # start không hợp lệ -> mặc định trái
    assert ScanRouter("xxx").route() == "left"

    print("TEST SCAN-ROUTER PASS ✔")


if __name__ == "__main__":
    main()
