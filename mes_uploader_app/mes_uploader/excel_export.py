# -*- coding: utf-8 -*-
"""Lưu giá trị đo của mỗi lần đọc ra file Excel (.xlsx) — KÈM cột SN.

Định dạng giống file đo gốc nhưng THÊM cột SN ở đầu:
    SN, Time, Judge, IspTime, Data01, Data02, ... DataN

- MỖI loại đầu (4X/8X/16X) lưu vào 1 THƯ MỤC RIÊNG do người dùng chọn (số cột
  Data mỗi loại khác nhau nên không trộn chung). Trong thư mục đó, mỗi NGÀY một
  thư mục con và mỗi BÊN (CCD1/CCD2) một file.
- Mỗi lần đọc (1 đầu) = 1 dòng được THÊM vào cuối; header chỉ viết khi tạo file.
- File: <thư mục loại đầu>/<YYYYMMDD>/<tên file đo gốc>.xlsx
- An toàn nhiều luồng (lock) — 2 bên ghi 2 file khác nhau, cùng file thì nối tiếp.

Module KHÔNG phụ thuộc Qt/PySide6 (để test headless và worker dùng được).
"""

import datetime
import os
import threading

from .i18n import tr

try:
    import openpyxl
except ImportError:                          # cho phép import khi chưa cài openpyxl
    openpyxl = None

_lock = threading.Lock()

# Các cột metadata đứng trước nhóm Data (SN thêm mới so với file gốc).
META_HEADERS = ["SN", "Time", "Judge", "IspTime"]


def output_path(out_dir, source_file, when=None):
    """Đường dẫn .xlsx đích: <out_dir>/<YYYYMMDD>/<tên file đo gốc>.xlsx.

    out_dir = thư mục đã chọn cho loại đầu tương ứng; mỗi ngày 1 thư mục con.
    """
    when = when or datetime.datetime.now()
    base = os.path.splitext(os.path.basename(source_file or "data"))[0] or "data"
    return os.path.join(out_dir, when.strftime("%Y%m%d"), base + ".xlsx")


def append_reading(out_path, sn, reading):
    """Thêm 1 dòng [SN, Time, Judge, IspTime, Data01..N] vào file Excel.

    Tạo file + dòng header (theo headers của reading) nếu chưa có. Cần openpyxl.
    Trả về out_path.
    """
    if openpyxl is None:
        raise RuntimeError(tr("Chưa cài thư viện 'openpyxl' để lưu Excel"))
    headers = list(reading.get("headers") or [])
    values = list(reading.get("values") or [])
    row = [sn, reading.get("time", ""), reading.get("judge", ""),
           reading.get("isp_time", "")] + values
    with _lock:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        if os.path.exists(out_path):
            wb = openpyxl.load_workbook(out_path)
            ws = wb.active
        else:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Data"
            ws.append(META_HEADERS + headers)   # SN + Time/Judge/IspTime + Data01..N
        ws.append(row)
        wb.save(out_path)
    return out_path
