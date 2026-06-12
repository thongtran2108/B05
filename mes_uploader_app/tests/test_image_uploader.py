# -*- coding: utf-8 -*-
"""Kiểm thử tải ảnh AOI (image_uploader) — không cần mạng / Qt / phần cứng.

Cấu trúc: <src>/Image/<YYYYMMDD>/<CCD1|CCD2>/<OK|NG>/  (CCD1=Trái, CCD2=Phải).
- Lấy ảnh MỚI NHẤT theo BÊN (CCD) + OK/NG.
- Copy sang <đích>/<YYYYMMDD>/<CCD>/ và đổi tên <SN>_<YYYY.MM.DD HH.MM.SS>_#<thứ tự đầu>.<ext>.
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
    src = os.path.join(root, "16X_RA-1")     # thư mục trạm (nguồn)
    dst = os.path.join(root, "upload16x")    # link đích (trạm)
    when = datetime.datetime(2026, 6, 9, 18, 34, 15)
    day = when.strftime("%Y%m%d")            # 20260609 (cả nguồn & đích)

    # Bên TRÁI = CCD1: thư mục OK có 2 ảnh (b.jpg mới hơn), NG có 1 ảnh
    ok1 = os.path.join(src, "Image", day, "CCD1", "OK")
    _mk(os.path.join(ok1, "a.jpg"), b"OLD", 1000)
    _mk(os.path.join(ok1, "b.jpg"), b"L_OK_NEW", 2000)
    _mk(os.path.join(src, "Image", day, "CCD1", "NG", "x.png"), b"L_NG", 1500)
    # Bên PHẢI = CCD2: 1 ảnh OK khác hẳn
    _mk(os.path.join(src, "Image", day, "CCD2", "OK", "r.jpg"), b"R_OK", 1700)

    # 1) build_dest_name: <SN>_<YYYY.MM.DD HH.MM.SS>_<Passed|Failed>_#<thứ tự đầu>
    print("== build_dest_name ==")
    assert iu.build_dest_name("123456", "OK", 1, ".jpg", when) == \
        "123456_2026.06.09 18.34.15_Passed_#1.jpg"
    assert iu.build_dest_name("9", "NG", 2, ".png", when) == \
        "9_2026.06.09 18.34.15_Failed_#2.png"

    # 2) find_latest_image theo BÊN (CCD): CCD1 lấy ảnh trái, CCD2 lấy ảnh phải
    print("\n== find_latest_image theo CCD ==")
    l_ok = iu.find_latest_image(src, "CCD1", "OK", when=when)
    assert os.path.basename(l_ok) == "b.jpg" and open(l_ok, "rb").read() == b"L_OK_NEW"
    r_ok = iu.find_latest_image(src, "CCD2", "OK", when=when)
    assert open(r_ok, "rb").read() == b"R_OK"   # đúng ảnh bên phải, không lẫn bên trái

    # 3) Tải ảnh CCD1 OK -> Passed, đầu #1: đích .../<YYYYMMDD>/CCD1/
    print("\n== upload CCD1 OK -> Passed, đầu #1 ==")
    ok, msg, dest = iu.upload_latest_image(src, dst, "CCD1", "123456", "OK",
                                           when=when, index=1)
    print(" ", ok, "|", msg)
    assert ok is True
    assert dest == os.path.join(dst, day, "CCD1",
                                "123456_2026.06.09 18.34.15_Passed_#1.jpg")
    assert open(dest, "rb").read() == b"L_OK_NEW"

    # 4) Tải ảnh CCD2 NG -> Failed, đầu #2, vào đúng CCD2 (giữ đuôi nguồn)
    print("\n== upload CCD2 NG -> Failed, đầu #2 ==")
    _mk(os.path.join(src, "Image", day, "CCD2", "NG", "rn.png"), b"R_NG", 1800)
    ok, msg, dest = iu.upload_latest_image(src, dst, "CCD2", "777", "NG",
                                           when=when, index=2)
    assert ok is True
    assert dest == os.path.join(dst, day, "CCD2",
                                "777_2026.06.09 18.34.15_Failed_#2.png")
    assert open(dest, "rb").read() == b"R_NG"

    # 5) Chưa cấu hình đích -> bỏ qua
    print("\n== chưa cấu hình -> bỏ qua ==")
    ok, _, dest = iu.upload_latest_image(src, "", "CCD1", "1", "OK", when=when)
    assert ok is False and dest is None

    # 6) Không có ảnh (ngày khác) -> bỏ qua
    print("\n== không có ảnh -> bỏ qua ==")
    when2 = datetime.datetime(2030, 1, 1, 0, 0, 0)
    ok, msg, dest = iu.upload_latest_image(src, dst, "CCD1", "1", "OK", when=when2)
    assert ok is False and dest is None
    print(" ", msg)

    # 7) Trùng tên (cùng SN + cùng đầu #1) -> tự thêm hậu tố, KHÔNG ghi đè
    print("\n== trùng tên -> không ghi đè ==")
    first = os.path.join(dst, day, "CCD1", "123456_2026.06.09 18.34.15_Passed_#1.jpg")
    ok2, _, dest2 = iu.upload_latest_image(src, dst, "CCD1", "123456", "OK",
                                           when=when, index=1)
    assert ok2 is True and dest2 != first and os.path.isfile(dest2) \
        and os.path.isfile(first)
    print("  ->", os.path.basename(dest2))

    # 8) fallback require_today=False: NGÀY (YYYYMMDD) mới nhất, bỏ thư mục rác
    print("\n== fallback: ngày mới nhất hợp lệ, bỏ thư mục rác ==")
    _mk(os.path.join(src, "Image", "20260601", "CCD1", "OK", "old.jpg"), b"OLDDAY", 8000)
    _mk(os.path.join(src, "Image", "zzzjunk", "CCD1", "OK", "junk.jpg"), b"JUNK", 9999)
    when3 = datetime.datetime(2027, 1, 1, 12, 0, 0)   # ngày chưa có thư mục
    l3 = iu.find_latest_image(src, "CCD1", "OK", when=when3, require_today=False)
    assert l3 and open(l3, "rb").read() == b"L_OK_NEW", l3   # = ngày 20260609
    assert iu.find_latest_image(src, "CCD1", "OK", when=when3,
                                require_today=True) is None

    print("\nTEST IMAGE-UPLOADER PASS ✔")


if __name__ == "__main__":
    main()
