# -*- coding: utf-8 -*-
"""Kiểm thử tải ảnh AOI (image_uploader) — không cần mạng / Qt / phần cứng.

- Lấy ảnh MỚI NHẤT trong thư mục OK/NG theo kết quả.
- Copy sang <đích>/<YYYYMMDD>/ và đổi tên
  <SN>_<YYYYMMDD HHMMSS>_Passed|Failed.<ext>.
- Bỏ qua khi chưa cấu hình / không có ảnh; trùng tên thì không ghi đè.

Chạy:  python -m tests.test_image_uploader
"""

import datetime
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader import image_uploader as iu


def _mk(path, data, mtime):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    os.utime(path, (mtime, mtime))


def main():
    root = tempfile.mkdtemp(prefix="img_test_")
    src = os.path.join(root, "src8x")
    dst = os.path.join(root, "upload8x")
    when = datetime.datetime(2026, 6, 9, 18, 34, 15)
    day_src = when.strftime("%Y-%m-%d")   # 2026-06-09 (thư mục ngày ở máy)
    day_dst = when.strftime("%Y%m%d")     # 20260609   (thư mục ngày ở đích)

    # Thư mục OK: 2 ảnh, b.jpg mới hơn a.jpg
    ok_dir = os.path.join(src, "Image", day_src, "OK")
    _mk(os.path.join(ok_dir, "a.jpg"), b"OLD", 1000)
    _mk(os.path.join(ok_dir, "b.jpg"), b"NEWEST", 2000)
    # Thư mục NG: 1 ảnh .png
    ng_dir = os.path.join(src, "Image", day_src, "NG")
    _mk(os.path.join(ng_dir, "x.png"), b"NGIMG", 1500)

    # 1) build_dest_name đúng định dạng yêu cầu
    print("== build_dest_name ==")
    name = iu.build_dest_name("123456", "OK", ".jpg", when)
    print(" ", name)
    assert name == "123456_20260609 183415_Passed.jpg", name
    assert iu.build_dest_name("9", "NG", ".png", when) == \
        "9_20260609 183415_Failed.png"

    # 2) find_latest_image lấy ảnh MỚI NHẤT
    print("\n== find_latest_image (mới nhất) ==")
    latest = iu.find_latest_image(src, "OK", when=when)
    print(" ", os.path.basename(latest))
    assert os.path.basename(latest) == "b.jpg"

    # 3) Tải ảnh OK -> Passed: đúng thư mục ngày + tên + nội dung ảnh mới nhất
    print("\n== upload OK -> Passed ==")
    ok, msg, dest = iu.upload_latest_image(src, dst, "123456", "OK", when=when)
    print(" ", ok, "|", msg)
    assert ok is True
    assert dest == os.path.join(dst, day_dst,
                                "123456_20260609 183415_Passed.jpg")
    assert os.path.isfile(dest)
    assert open(dest, "rb").read() == b"NEWEST"      # đúng ảnh mới nhất

    # 4) Tải ảnh NG -> Failed: giữ phần mở rộng nguồn (.png)
    print("\n== upload NG -> Failed ==")
    ok, msg, dest = iu.upload_latest_image(src, dst, "777", "NG", when=when)
    assert ok is True and dest.endswith("777_20260609 183415_Failed.png")
    assert open(dest, "rb").read() == b"NGIMG"

    # 5) Chưa cấu hình đích -> bỏ qua (không lỗi, không copy)
    print("\n== chưa cấu hình -> bỏ qua ==")
    ok, msg, dest = iu.upload_latest_image(src, "", "1", "OK", when=when)
    assert ok is False and dest is None
    print(" ", msg)

    # 6) Không có ảnh (ngày khác, không có thư mục) -> bỏ qua
    print("\n== không có ảnh -> bỏ qua ==")
    when2 = datetime.datetime(2030, 1, 1, 0, 0, 0)
    ok, msg, dest = iu.upload_latest_image(src, dst, "1", "OK", when=when2)
    assert ok is False and dest is None
    print(" ", msg)

    # 7) Trùng tên -> tự thêm hậu tố, KHÔNG ghi đè ảnh cũ
    print("\n== trùng tên -> không ghi đè ==")
    first = os.path.join(dst, day_dst, "123456_20260609 183415_Passed.jpg")
    ok2, _, dest2 = iu.upload_latest_image(src, dst, "123456", "OK", when=when)
    assert ok2 is True and dest2 != first and os.path.isfile(dest2)
    assert os.path.isfile(first)                      # ảnh cũ còn nguyên
    print("  ->", os.path.basename(dest2))

    print("\nTEST IMAGE-UPLOADER PASS ✔")


if __name__ == "__main__":
    main()
