# -*- coding: utf-8 -*-
"""Tìm ảnh AOI MỚI NHẤT theo kết quả OK/NG rồi "tải lên" (copy) sang link đích.

Cấu trúc thư mục ảnh ở máy (riêng theo từng loại đầu 4X/8X/16X):

    <source_dir>/<sub_image>/<YYYY-MM-DD>/<OK|NG>/   -> các file ảnh

Khi nhận kết quả OK / NG của 1 đầu:
    - vào đúng thư mục OK hoặc NG của NGÀY HÔM NAY (vd 2026-06-09)
    - lấy ảnh MỚI NHẤT (theo thời gian sửa đổi)
    - copy sang  <upload_dir>/<YYYYMMDD>/  (tạo thư mục ngày nếu chưa có)
    - đổi tên:  <SN>_<YYYYMMDD HHMMSS>_<Passed|Failed>.<ext>
                vd  123456_20260609 183415_Passed.jpg   (Passed=OK, Failed=NG)

"Tải lên" = copy file sang đường dẫn chia sẻ mạng (UNC), vd
//10.222.48.222/AOI/17G — ghi thẳng vào share nếu máy có quyền truy cập.

Module KHÔNG phụ thuộc Qt/PySide6 để test headless và worker dùng được.
"""

import datetime
import os
import shutil

from .i18n import tr

# Phần mở rộng ảnh mặc định khi không cấu hình (so khớp không phân biệt hoa/thường).
DEFAULT_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp")


def passed_label(judge):
    """OK -> 'Passed'; còn lại (NG…) -> 'Failed'."""
    return "Passed" if str(judge).strip().upper() == "OK" else "Failed"


def _src_day(when):
    return when.strftime("%Y-%m-%d")        # thư mục ngày ở máy: 2026-06-09


def _dst_day(when):
    return when.strftime("%Y%m%d")          # thư mục ngày ở đích: 20260609


def _stamp(when):
    return when.strftime("%Y%m%d %H%M%S")   # phần thời gian trong tên: 20260609 183415


def build_dest_name(sn, judge, ext=".jpg", when=None):
    """Tên file đích: <sn>_<YYYYMMDD HHMMSS>_<Passed|Failed><ext>."""
    when = when or datetime.datetime.now()
    if ext and not ext.startswith("."):
        ext = "." + ext
    return "%s_%s_%s%s" % (sn, _stamp(when), passed_label(judge), ext or ".jpg")


def _judge_dir(source_dir, judge, when, sub_image, ok_dir, ng_dir,
               require_today):
    """Thư mục ảnh OK/NG tương ứng của ngày yêu cầu.

    require_today=True  -> chỉ dùng thư mục NGÀY HÔM NAY; thiếu -> None.
    require_today=False -> nếu thiếu hôm nay thì lùi về thư mục ngày mới nhất
                           có chứa thư mục con OK/NG tương ứng.
    Trả về đường dẫn thư mục, hoặc None nếu không có.
    """
    leaf = ok_dir if str(judge).strip().upper() == "OK" else ng_dir
    img_root = os.path.join(source_dir, sub_image)
    today_dir = os.path.join(img_root, _src_day(when), leaf)
    if os.path.isdir(today_dir):
        return today_dir
    if require_today or not os.path.isdir(img_root):
        return None
    # fallback: thư mục ngày mới nhất CÓ chứa thư mục con OK/NG cần lấy
    for day in sorted((d for d in os.listdir(img_root)
                       if os.path.isdir(os.path.join(img_root, d))),
                      reverse=True):
        cand = os.path.join(img_root, day, leaf)
        if os.path.isdir(cand):
            return cand
    return None


def find_latest_image(source_dir, judge, when=None, sub_image="Image",
                      ok_dir="OK", ng_dir="NG", extensions=DEFAULT_EXTENSIONS,
                      require_today=True):
    """Trả về đường dẫn ảnh MỚI NHẤT trong thư mục OK/NG tương ứng, hoặc None."""
    when = when or datetime.datetime.now()
    d = _judge_dir(source_dir, judge, when, sub_image, ok_dir, ng_dir,
                   require_today)
    if not d:
        return None
    exts = {e.lower() for e in (extensions or DEFAULT_EXTENSIONS)}
    files = [os.path.join(d, n) for n in os.listdir(d)]
    files = [f for f in files
             if os.path.isfile(f) and os.path.splitext(f)[1].lower() in exts]
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def _unique_path(path):
    """Nếu 'path' đã tồn tại, chèn _1, _2… trước phần mở rộng để không ghi đè."""
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    i = 1
    while True:
        cand = "%s_%d%s" % (root, i, ext)
        if not os.path.exists(cand):
            return cand
        i += 1


def upload_latest_image(source_dir, upload_dir, sn, judge, when=None,
                        sub_image="Image", ok_dir="OK", ng_dir="NG",
                        extensions=DEFAULT_EXTENSIONS, require_today=True):
    """Tìm ảnh mới nhất theo OK/NG ở 'source_dir' rồi copy sang
    '<upload_dir>/<YYYYMMDD>/' với tên đã đổi.

    Trả về (ok: bool, message: str, dest_path: str | None).
    """
    when = when or datetime.datetime.now()
    if not source_dir or not upload_dir:
        return False, tr("Chưa cấu hình thư mục ảnh nguồn/đích"), None
    src = find_latest_image(source_dir, judge, when, sub_image, ok_dir, ng_dir,
                            extensions, require_today)
    if not src:
        where = os.path.join(source_dir, sub_image, _src_day(when),
                             ok_dir if str(judge).strip().upper() == "OK"
                             else ng_dir)
        return False, tr("Không tìm thấy ảnh mới trong %s") % where, None
    ext = os.path.splitext(src)[1] or ".jpg"
    day_dir = os.path.join(upload_dir, _dst_day(when))
    try:
        os.makedirs(day_dir, exist_ok=True)
        dest = _unique_path(os.path.join(
            day_dir, build_dest_name(sn, judge, ext, when)))
        shutil.copy2(src, dest)
    except Exception as ex:                  # noqa: BLE001  (lỗi mạng/quyền)
        return False, tr("Lỗi copy ảnh lên '%s': %s") % (upload_dir, ex), None
    return True, tr("Đã tải ảnh %s") % os.path.basename(dest), dest
