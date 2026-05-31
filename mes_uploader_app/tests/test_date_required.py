# -*- coding: utf-8 -*-
"""Kiểm thử đọc dữ liệu THEO NGÀY: có thư mục ngày hôm nay thì đọc, thiếu thì lỗi.

Chạy:  python -m tests.test_date_required
"""

import datetime
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader import data_reader
from mes_uploader.data_reader import DataNotAvailableError
from mes_uploader.config import PathConfig, SideConfig

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "sample_data")
LEFT = SideConfig(name="LEFT", ccd_prefix="CCD1")
RIGHT = SideConfig(name="RIGHT", ccd_prefix="CCD2")


def _make_tree(with_today):
    """Tạo cây dữ liệu tạm; tùy chọn có hay không thư mục ngày hôm nay."""
    root = tempfile.mkdtemp(prefix="mes_date_")
    today = datetime.date.today().strftime("%Y%m%d")
    src_day = os.path.join(SAMPLE, "8X", "data", "20260528")
    for sub in ("8X/data", "16X/data"):
        # luôn có 1 ngày cũ
        old = os.path.join(root, sub, "20200101")
        os.makedirs(old)
        for f in os.listdir(src_day):
            shutil.copy(os.path.join(src_day, f), os.path.join(old, f))
        if with_today:
            new = os.path.join(root, sub, today)
            os.makedirs(new)
            for f in os.listdir(src_day):
                shutil.copy(os.path.join(src_day, f), os.path.join(new, f))
    return root, today


def main():
    # 1) Có thư mục ngày hôm nay -> đọc OK, và đúng là file của ngày hôm nay
    root, today = _make_tree(with_today=True)
    paths = PathConfig(base_dir=root)
    r = data_reader.get_latest_for_side(paths, LEFT, "8X", require_today=True)
    assert today in r["file"], "Phải đọc file trong thư mục ngày hôm nay"
    assert len(r["values"]) > 0
    print("1) Có ngày hôm nay -> đọc OK:", os.path.relpath(r["file"], root))
    shutil.rmtree(root, ignore_errors=True)

    # 2) KHÔNG có thư mục ngày hôm nay -> báo lỗi (không lấy ngày cũ)
    root, today = _make_tree(with_today=False)
    paths = PathConfig(base_dir=root)
    try:
        data_reader.get_latest_for_side(paths, LEFT, "8X", require_today=True)
        raise AssertionError("Phải ném DataNotAvailableError khi thiếu ngày hôm nay")
    except DataNotAvailableError as ex:
        assert today in str(ex)
        print("2) Thiếu ngày hôm nay -> báo lỗi đúng:", str(ex).splitlines()[0])

    # 3) require_today=False -> fallback lấy ngày mới nhất (ngày cũ 20200101)
    r = data_reader.get_latest_for_side(paths, LEFT, "8X", require_today=False)
    assert "20200101" in r["file"]
    print("3) require_today=False -> fallback ngày cũ:", os.path.relpath(r["file"], root))

    # 4) Có thư mục ngày hôm nay nhưng THIẾU file CCD -> báo lỗi
    empty_day = os.path.join(root, "8X/data", today)
    os.makedirs(empty_day, exist_ok=True)   # thư mục rỗng, không có CCD1*
    try:
        data_reader.get_latest_for_side(paths, LEFT, "8X", require_today=True)
        raise AssertionError("Phải ném lỗi khi thư mục ngày hôm nay không có file")
    except DataNotAvailableError as ex:
        assert "CCD1" in str(ex)
        print("4) Có thư mục ngày nhưng thiếu file -> báo lỗi đúng")
    shutil.rmtree(root, ignore_errors=True)

    print("\nTEST DATE-REQUIRED PASS ✔")


if __name__ == "__main__":
    main()
