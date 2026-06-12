# -*- coding: utf-8 -*-
"""Tìm ảnh AOI MỚI NHẤT theo BÊN (CCD) + kết quả OK/NG rồi copy sang link đích.

Cấu trúc thư mục ảnh ở máy (riêng theo từng loại đầu):

    <source_dir>/<sub_image>/<YYYYMMDD>/<CCD1|CCD2>/<OK|NG>/  -> các file ảnh

    CCD1 = bên TRÁI, CCD2 = bên PHẢI; OK/NG theo judge.

Khi 1 đầu chạy xong:
    - vào đúng <YYYYMMDD>/<CCD bên đó>/<OK|NG> của NGÀY HÔM NAY
    - lấy ảnh MỚI NHẤT (theo thời gian sửa đổi)
    - copy sang  <upload_dir>/<YYYYMMDD>/<CCD>/  (tạo thư mục nếu chưa có)
    - đổi tên:  <SN>_<YYYY.MM.DD HH.MM.SS>_#<thứ tự đầu>.<ext>
                vd  123456_2026.06.09 18.34.15_#1.jpg
                (#1, #2… theo từng đầu đo của SN — 2 đầu 8X -> _#1 và _#2)

"Tải lên" = copy file sang đường dẫn chia sẻ mạng (UNC), vd
//10.222.48.222/<tên trạm> — ghi thẳng vào share nếu máy có quyền.

Module KHÔNG phụ thuộc Qt/PySide6 để test headless và worker dùng được.
"""

import datetime
import os
import shutil

from .i18n import tr

# Phần mở rộng ảnh mặc định khi không cấu hình (so khớp không phân biệt hoa/thường).
DEFAULT_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp")


def _day(when):
    return when.strftime("%Y%m%d")          # thư mục ngày: 20260606 (cả nguồn & đích)


def _stamp(when):
    return when.strftime("%Y.%m.%d %H.%M.%S")  # phần thời gian trong tên: 2026.06.09 18.34.15


def build_dest_name(sn, index, ext=".jpg", when=None):
    """Tên file đích: <sn>_<YYYY.MM.DD HH.MM.SS>_#<số thứ tự đầu><ext>.

    index = thứ tự đầu đo của SN này (1, 2, …). Khi 1 SN có nhiều đầu thì ảnh
    mỗi đầu có tên khác nhau (vd 2 đầu 8X -> _#1, _#2) nên không ghi đè nhau.
    """
    when = when or datetime.datetime.now()
    if ext and not ext.startswith("."):
        ext = "." + ext
    return "%s_%s_#%d%s" % (sn, _stamp(when), int(index), ext or ".jpg")


def _leaf_for(judge, ok_dir, ng_dir):
    """Thư mục con theo kết quả: OK -> ok_dir, còn lại -> ng_dir."""
    return ok_dir if str(judge).strip().upper() == "OK" else ng_dir


def _is_day_name(name):
    """Tên thư mục có đúng định dạng ngày YYYYMMDD không."""
    try:
        datetime.datetime.strptime(name, "%Y%m%d")
        return True
    except ValueError:
        return False


def _judge_dir(source_dir, ccd, judge, when, sub_image, ok_dir, ng_dir,
               require_today):
    """Thư mục ảnh: <source_dir>/<sub_image>/<YYYYMMDD>/<CCD>/<OK|NG>.

    ccd = 'CCD1' (Trái) / 'CCD2' (Phải). leaf = OK/NG theo judge.
    require_today=True  -> chỉ dùng thư mục NGÀY HÔM NAY; thiếu -> None.
    require_today=False -> nếu thiếu hôm nay thì lùi về NGÀY (YYYYMMDD) mới nhất
                           có sẵn .../CCD/OK|NG.
    Trả về đường dẫn thư mục, hoặc None nếu không có.
    """
    leaf = _leaf_for(judge, ok_dir, ng_dir)
    img_root = os.path.join(source_dir, sub_image)
    today_dir = os.path.join(img_root, _day(when), ccd, leaf)
    if os.path.isdir(today_dir):
        return today_dir
    if require_today:
        return None
    # fallback: thư mục NGÀY (YYYYMMDD) mới nhất có sẵn <CCD>/<OK|NG>
    try:
        days = sorted(
            (d for d in os.listdir(img_root)
             if _is_day_name(d)
             and os.path.isdir(os.path.join(img_root, d, ccd, leaf))),
            reverse=True)
    except OSError:                          # img_root không có / share lỗi
        return None
    return os.path.join(img_root, days[0], ccd, leaf) if days else None


def _safe_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:                          # file biến mất giữa chừng
        return -1.0


def _latest_in_dir(d, extensions):
    """Ảnh mới nhất (theo mtime) trong thư mục d, hoặc None.

    An toàn với race trên share: listdir/getmtime lỗi -> None / bỏ qua file đó.
    """
    if not d:
        return None
    exts = {e.lower() for e in (extensions or DEFAULT_EXTENSIONS)}
    try:
        names = os.listdir(d)
    except OSError:                          # thư mục biến mất / share lỗi
        return None
    files = [os.path.join(d, n) for n in names]
    files = [f for f in files
             if os.path.splitext(f)[1].lower() in exts and os.path.isfile(f)]
    if not files:
        return None
    return max(files, key=_safe_mtime)


def find_latest_image(source_dir, ccd, judge, when=None, sub_image="Image",
                      ok_dir="OK", ng_dir="NG", extensions=DEFAULT_EXTENSIONS,
                      require_today=True):
    """Ảnh MỚI NHẤT trong <source_dir>/<sub_image>/<YYYYMMDD>/<CCD>/<OK|NG>."""
    when = when or datetime.datetime.now()
    d = _judge_dir(source_dir, ccd, judge, when, sub_image, ok_dir, ng_dir,
                   require_today)
    return _latest_in_dir(d, extensions)


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


def upload_latest_image(source_dir, upload_dir, ccd, sn, judge, when=None,
                        sub_image="Image", ok_dir="OK", ng_dir="NG",
                        extensions=DEFAULT_EXTENSIONS, require_today=True,
                        index=1):
    """Lấy ảnh mới nhất ở <source_dir>/<sub_image>/<YYYYMMDD>/<CCD>/<OK|NG>
    rồi copy sang <upload_dir>/<YYYYMMDD>/<CCD>/ với tên đã đổi.

    ccd = 'CCD1' (Trái) / 'CCD2' (Phải). judge (OK/NG) dùng để chọn thư mục
    nguồn; index = thứ tự đầu đo của SN (1, 2, …) -> đưa vào tên file (_#index).
    Trả về (ok: bool, message: str, dest_path: str | None).
    """
    when = when or datetime.datetime.now()
    if not source_dir or not upload_dir:
        return False, tr("Chưa cấu hình thư mục ảnh nguồn/đích"), None
    d = _judge_dir(source_dir, ccd, judge, when, sub_image, ok_dir, ng_dir,
                   require_today)
    src = _latest_in_dir(d, extensions)
    if not src:
        # báo đúng thư mục đã tìm (kể cả khi fallback sang ngày cũ)
        where = d or os.path.join(source_dir, sub_image, _day(when), ccd,
                                  _leaf_for(judge, ok_dir, ng_dir))
        return False, tr("Không tìm thấy ảnh mới trong %s") % where, None
    ext = os.path.splitext(src)[1] or ".jpg"
    day_dir = os.path.join(upload_dir, _day(when), ccd)
    try:
        os.makedirs(day_dir, exist_ok=True)
        dest = _unique_path(os.path.join(
            day_dir, build_dest_name(sn, index, ext, when)))
        # copy (không phải copy2): để mtime đích = lúc tải, dễ sắp xếp ở đích
        shutil.copy(src, dest)
    except Exception as ex:                  # noqa: BLE001  (lỗi mạng/quyền)
        return False, tr("Lỗi copy ảnh lên '%s': %s") % (upload_dir, ex), None
    return True, tr("Đã tải ảnh %s") % os.path.basename(dest), dest
