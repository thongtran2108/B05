# -*- coding: utf-8 -*-
"""Đọc dòng dữ liệu MỚI NHẤT trong file đo của 1 bên (CCD1 / CCD2).

Cấu trúc file (xác minh từ dữ liệu mẫu):
    Time, Judge, IspTime, Data01, Data02, ... DataNN
    - Time    : thời gian đo
    - Judge   : kết quả OK / NG   (phần "jugle" theo yêu cầu)
    - IspTime : thời gian kiểm (ms)
    - DataNN  : các giá trị đo (số cột thay đổi tùy file, KHÔNG hardcode)

Lưu ý: trong dữ liệu mẫu, có file mang đuôi .csv nhưng thực chất là XLSX
(file ZIP, bắt đầu bằng 'PK'). Vì vậy ở đây TỰ NHẬN DIỆN theo nội dung
chứ không dựa vào đuôi file.

"Lấy nội dung mới nhất" = lấy DÒNG DỮ LIỆU CUỐI CÙNG của file mới nhất
(trong thư mục ngày mới nhất).
"""

import csv
import datetime
import glob
import io
import os


class DataNotAvailableError(IOError):
    """Không có dữ liệu cho ngày yêu cầu (thiếu thư mục ngày / thiếu file /
    file chưa có dòng dữ liệu). Dùng để báo lỗi rõ ràng lên giao diện."""


def today_str():
    """Chuỗi ngày hôm nay dạng YYYYMMDD (khớp tên thư mục theo ngày)."""
    return datetime.date.today().strftime("%Y%m%d")


# ---------------------------------------------------------------------- #
#  Đọc thô toàn bộ dòng (header + data) — tự nhận diện CSV / XLSX         #
# ---------------------------------------------------------------------- #
def _read_rows(path):
    with open(path, "rb") as f:
        signature = f.read(4)
    if signature[:2] == b"PK":          # ZIP -> file XLSX (kể cả đuôi .csv)
        return _read_xlsx(path)
    return _read_csv(path)


def _read_csv(path):
    """Đọc CSV, thử lần lượt nhiều bảng mã hay gặp."""
    raw = open(path, "rb").read()
    last_err = None
    for enc in ("utf-8-sig", "gb18030", "utf-16", "latin-1"):
        try:
            text = raw.decode(enc)
            return [row for row in csv.reader(io.StringIO(text))]
        except Exception as ex:        # noqa: BLE001
            last_err = ex
    raise IOError("Khong doc duoc CSV %s: %s" % (path, last_err))


def _read_xlsx(path):
    """Đọc XLSX qua openpyxl. Truyền BytesIO để bỏ qua kiểm tra đuôi file."""
    try:
        import openpyxl
    except ImportError as ex:
        raise IOError("Can cai 'openpyxl' de doc file Excel: %s" % ex)
    data = open(path, "rb").read()
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        ws = wb.active
        rows = []
        for r in ws.iter_rows(values_only=True):
            rows.append(["" if c is None else c for c in r])
        return rows
    finally:
        wb.close()


# ---------------------------------------------------------------------- #
#  Tìm file mới nhất của 1 bên trong thư mục theo ngày                    #
# ---------------------------------------------------------------------- #
def find_latest_file(type_dir, name_glob):
    """Tìm file mới nhất khớp 'name_glob' (vd 'CCD1*') trong type_dir.

    type_dir thường có cấu trúc <type_dir>/<YYYYMMDD>/CCD1*. Chọn thư mục
    ngày mới nhất trước, nếu không có thì tìm thẳng trong type_dir.
    Trả về đường dẫn file, hoặc None nếu không tìm thấy.
    """
    if not os.path.isdir(type_dir):
        return None

    # các thư mục con (theo ngày) sắp xếp giảm dần -> ngày mới nhất trước
    subdirs = sorted(
        (d for d in os.listdir(type_dir)
         if os.path.isdir(os.path.join(type_dir, d))),
        reverse=True,
    )
    search_dirs = [os.path.join(type_dir, d) for d in subdirs]
    search_dirs.append(type_dir)        # fallback: tìm thẳng trong type_dir

    for d in search_dirs:
        matches = glob.glob(os.path.join(d, name_glob))
        matches = [m for m in matches if os.path.isfile(m)]
        if matches:
            # file mới nhất theo thời gian sửa đổi
            return max(matches, key=os.path.getmtime)
    return None


# ---------------------------------------------------------------------- #
#  Lấy dòng dữ liệu mới nhất                                              #
# ---------------------------------------------------------------------- #
def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def read_latest_measurement(path):
    """Đọc dòng cuối cùng của file, tách Judge và các giá trị Data01..N.

    Trả về dict:
      {
        "time":    str,
        "judge":   str (OK/NG),
        "values":  [float, ...]   # chỉ các cột Data01..N
        "headers": [str, ...]     # tên cột của các giá trị (Data01..N)
        "raw":     [...]          # nguyên dòng cuối
        "file":    path
      }
    """
    rows = _read_rows(path)
    if not rows:
        raise DataNotAvailableError("File rỗng: %s" % path)

    header = [str(h).strip() for h in rows[0]]

    # vị trí các cột giá trị đo = cột có tên bắt đầu bằng "Data"
    data_idx = [i for i, h in enumerate(header) if h.lower().startswith("data")]
    # nếu không nhận ra theo tên (file lạ) -> coi từ cột thứ 4 trở đi là data
    if not data_idx:
        data_idx = list(range(3, len(header)))

    try:
        judge_idx = next(i for i, h in enumerate(header)
                         if h.lower() in ("judge", "jugle", "result"))
    except StopIteration:
        judge_idx = 1 if len(header) > 1 else 0

    # dòng dữ liệu cuối cùng (bỏ qua dòng trống)
    data_rows = [r for r in rows[1:] if r and any(str(c).strip() for c in r)]
    if not data_rows:
        raise DataNotAvailableError("File chưa có dòng dữ liệu: %s" % path)
    last = data_rows[-1]

    def get(idx):
        return last[idx] if idx < len(last) else ""

    values = [_to_float(get(i)) for i in data_idx]
    return {
        "time": str(get(0)),
        "judge": str(get(judge_idx)).strip(),
        "values": values,
        "headers": [header[i] for i in data_idx],
        "raw": list(last),
        "file": path,
    }


def get_latest_for_side(paths_cfg, side_cfg, head_type, require_today=True,
                        today=None):
    """Gộp tìm file + đọc dòng mới nhất cho 1 bên + 1 loại đầu.

    paths_cfg     : PathConfig
    side_cfg      : SideConfig (lấy ccd_prefix -> chọn glob trái/phải)
    head_type     : '4X', '8X' hoặc '16X'
    require_today : True  -> CHỈ đọc thư mục ngày hôm nay; thiếu thì báo lỗi
                            (không lấy nhầm dữ liệu của ngày cũ).
                    False -> lấy file mới nhất ở thư mục ngày mới nhất (fallback).
    today         : ghi đè ngày (YYYYMMDD) để kiểm thử; mặc định = hôm nay.

    Ném DataNotAvailableError nếu không có dữ liệu hợp lệ cho ngày yêu cầu.
    """
    if head_type == "4X":
        sub = paths_cfg.sub_4x
    elif head_type == "8X":
        sub = paths_cfg.sub_8x
    else:
        sub = paths_cfg.sub_16x
    type_dir = os.path.join(paths_cfg.base_dir, sub)
    name_glob = (paths_cfg.left_glob if side_cfg.ccd_prefix.upper() == "CCD1"
                 else paths_cfg.right_glob)

    if require_today:
        day = today or today_str()
        day_dir = os.path.join(type_dir, day)
        if not os.path.isdir(day_dir):
            raise DataNotAvailableError(
                "Chưa có dữ liệu cho ngày hôm nay (%s).\n"
                "Thiếu thư mục: %s" % (day, day_dir))
        matches = [m for m in glob.glob(os.path.join(day_dir, name_glob))
                   if os.path.isfile(m)]
        if not matches:
            raise DataNotAvailableError(
                "Ngày hôm nay (%s) chưa có file '%s'.\n"
                "Trong thư mục: %s" % (day, name_glob, day_dir))
        path = max(matches, key=os.path.getmtime)
    else:
        path = find_latest_file(type_dir, name_glob)
        if path is None:
            raise DataNotAvailableError(
                "Không tìm thấy file '%s' trong %s" % (name_glob, type_dir))

    return read_latest_measurement(path)
