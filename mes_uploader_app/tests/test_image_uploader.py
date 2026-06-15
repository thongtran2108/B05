# -*- coding: utf-8 -*-
"""Kiểm thử tải ảnh AOI (image_uploader) — không cần mạng / Qt / phần cứng.

Cấu trúc: <src>/Image/<YYYYMMDD>/<CCD1|CCD2>/<OK|NG>/  (CCD1=Trái, CCD2=Phải).
- Lấy ảnh MỚI NHẤT theo BÊN (CCD) + OK/NG.
- Tải sang <đích>/<YYYYMMDD>/ (KHÔNG chia thư mục CCD) và đổi tên
  <SN>_<YYYY.MM.DD HH.MM.SS>_<Left|Right>_Passed|Failed_#<thứ tự đầu>.jpg
  (Left=CCD1, Right=CCD2).
- Ảnh tải lên LUÔN là .jpg: nguồn .jpg giữ nguyên (copy), PNG/BMP… -> nén .jpg.
- Bỏ qua khi chưa cấu hình / không có ảnh; trùng tên thì không ghi đè.

Chạy:  python -m tests.test_image_uploader
"""

import datetime
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from mes_uploader import image_uploader as iu


def _mkimg(path, size, fmt, mtime):
    """Tạo 1 ảnh THẬT (kích thước riêng để phân biệt) rồi đặt mtime."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new("RGB", size, (30, 120, 200)).save(path, fmt)
    os.utime(path, (mtime, mtime))


def _jpg(path):
    """Mở ảnh và khẳng định là JPEG; trả về kích thước (để so khớp đúng ảnh)."""
    with Image.open(path) as im:
        assert im.format == "JPEG", "%s không phải JPEG (%s)" % (path, im.format)
        return im.size


def main():
    root = tempfile.mkdtemp(prefix="img_test_")
    src = os.path.join(root, "16X_RA-1")     # thư mục trạm (nguồn)
    dst = os.path.join(root, "upload16x")    # link đích (trạm)
    when = datetime.datetime(2026, 6, 9, 18, 34, 15)
    day = when.strftime("%Y%m%d")            # 20260609 (cả nguồn & đích)

    # Bên TRÁI = CCD1: OK có 2 ảnh JPG (b.jpg mới hơn, 14x14), NG 1 ảnh PNG
    ok1 = os.path.join(src, "Image", day, "CCD1", "OK")
    _mkimg(os.path.join(ok1, "a.jpg"), (10, 10), "JPEG", 1000)
    _mkimg(os.path.join(ok1, "b.jpg"), (14, 14), "JPEG", 2000)
    _mkimg(os.path.join(src, "Image", day, "CCD1", "NG", "x.png"), (11, 11), "PNG", 1500)
    # Bên PHẢI = CCD2: 1 ảnh OK kích thước khác hẳn (20x20)
    _mkimg(os.path.join(src, "Image", day, "CCD2", "OK", "r.jpg"), (20, 20), "JPEG", 1700)

    # 1) side_label + build_dest_name: chèn Left/Right NGAY TRƯỚC Passed/Failed
    print("== side_label + build_dest_name ==")
    assert iu.side_label("CCD1") == "Left" and iu.side_label("CCD2") == "Right"
    assert iu.side_label("CCDx") == ""       # CCD lạ -> không chèn nhãn bên
    assert iu.build_dest_name("123456", "OK", 1, ".jpg", when, side="Left") == \
        "123456_2026.06.09 18.34.15_Left_Passed_#1.jpg"
    assert iu.build_dest_name("9", "NG", 2, ".jpg", when, side="Right") == \
        "9_2026.06.09 18.34.15_Right_Failed_#2.jpg"
    # không truyền side -> tương thích ngược (không chèn Left/Right)
    assert iu.build_dest_name("9", "NG", 2, ".jpg", when) == \
        "9_2026.06.09 18.34.15_Failed_#2.jpg"

    # 2) find_latest_image theo BÊN (CCD): CCD1 lấy ảnh trái (14x14), CCD2 (20x20)
    print("\n== find_latest_image theo CCD ==")
    l_ok = iu.find_latest_image(src, "CCD1", "OK", when=when)
    assert os.path.basename(l_ok) == "b.jpg" and _jpg(l_ok) == (14, 14)
    r_ok = iu.find_latest_image(src, "CCD2", "OK", when=when)
    assert _jpg(r_ok) == (20, 20)            # đúng ảnh bên phải, không lẫn bên trái

    # 3) Tải ảnh CCD1 OK -> Left_Passed, đầu #1 (nguồn .jpg -> copy giữ nguyên)
    print("\n== upload CCD1 OK -> Left_Passed, đầu #1 ==")
    ok, msg, dest = iu.upload_latest_image(src, dst, "CCD1", "123456", "OK",
                                           when=when, index=1)
    print(" ", ok, "|", msg)
    assert ok is True
    assert dest == os.path.join(dst, day,
                                "123456_2026.06.09 18.34.15_Left_Passed_#1.jpg")
    assert _jpg(dest) == (14, 14)

    # 4) Tải ảnh CCD2 NG -> Right_Failed, đầu #2: nguồn PNG -> NÉN sang .jpg
    print("\n== upload CCD2 NG -> Right_Failed, đầu #2 (PNG -> .jpg) ==")
    _mkimg(os.path.join(src, "Image", day, "CCD2", "NG", "rn.png"), (12, 12), "PNG", 1800)
    ok, msg, dest = iu.upload_latest_image(src, dst, "CCD2", "777", "NG",
                                           when=when, index=2, jpeg_quality=70)
    assert ok is True
    assert dest == os.path.join(dst, day,
                                "777_2026.06.09 18.34.15_Right_Failed_#2.jpg")
    assert _jpg(dest) == (12, 12)            # ảnh đã chuyển sang JPEG, giữ kích thước

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
    first = os.path.join(dst, day, "123456_2026.06.09 18.34.15_Left_Passed_#1.jpg")
    ok2, _, dest2 = iu.upload_latest_image(src, dst, "CCD1", "123456", "OK",
                                           when=when, index=1)
    assert ok2 is True and dest2 != first and os.path.isfile(dest2) \
        and os.path.isfile(first)
    print("  ->", os.path.basename(dest2))

    # 8) fallback require_today=False: NGÀY (YYYYMMDD) mới nhất, bỏ thư mục rác
    print("\n== fallback: ngày mới nhất hợp lệ, bỏ thư mục rác ==")
    _mkimg(os.path.join(src, "Image", "20260601", "CCD1", "OK", "old.jpg"), (9, 9), "JPEG", 8000)
    _mkimg(os.path.join(src, "Image", "zzzjunk", "CCD1", "OK", "junk.jpg"), (8, 8), "JPEG", 9999)
    when3 = datetime.datetime(2027, 1, 1, 12, 0, 0)   # ngày chưa có thư mục
    l3 = iu.find_latest_image(src, "CCD1", "OK", when=when3, require_today=False)
    assert l3 and _jpg(l3) == (14, 14), l3   # = ngày 20260609 (b.jpg)
    assert iu.find_latest_image(src, "CCD1", "OK", when=when3,
                                require_today=True) is None

    print("\nTEST IMAGE-UPLOADER PASS ✔")


if __name__ == "__main__":
    main()
