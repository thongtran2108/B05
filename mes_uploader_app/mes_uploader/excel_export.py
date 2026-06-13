# -*- coding: utf-8 -*-
"""Lưu giá trị đo của mỗi lần đọc ra file Excel (.xlsx) — KÈM cột SN.

Định dạng giống file đo gốc nhưng THÊM cột SN ở đầu:
    SN, Time, Judge, IspTime, Data01, Data02, ... DataN

- Mỗi bên (CCD1/CCD2) 1 file theo NGÀY, cùng tên với file đo gốc.
- Mỗi lần đọc (1 đầu) = 1 dòng được THÊM vào cuối; header chỉ viết khi tạo file.
- File: <output_dir>/<YYYYMMDD>/<tên file đo gốc>.xlsx
- An toàn nhiều luồng (lock) — 2 bên ghi 2 file khác nhau, cùng file thì nối tiếp.

Module KHÔNG phụ thuộc Qt/PySide6 (để test headless và worker dùng được).
"""

import datetime
import os
import sys
import threading

from .i18n import tr

try:
    import openpyxl
except ImportError:                          # cho phép import khi chưa cài openpyxl
    openpyxl = None

_lock = threading.Lock()

# Các cột metadata đứng trước nhóm Data (SN thêm mới so với file gốc).
META_HEADERS = ["SN", "Time", "Judge", "IspTime"]


def default_output_dir():
    """Thư mục mặc định = 'excel_data' cạnh ứng dụng (exe hoặc thư mục run.py)."""
    if getattr(sys, "frozen", False):        # bản đóng gói PyInstaller
        base = os.path.dirname(sys.executable)
    else:                                    # chạy mã nguồn: .../mes_uploader_app
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "excel_data")


def resolve_output_dir(cfg):
    """Thư mục lưu Excel từ cấu hình: cfg.excel.output_dir nếu có, ngược lại mặc định."""
    d = (getattr(getattr(cfg, "excel", None), "output_dir", "") or "").strip()
    return d or default_output_dir()


def output_path(output_dir, source_file, when=None):
    """Đường dẫn file .xlsx đích: <output_dir>/<YYYYMMDD>/<tên file gốc>.xlsx."""
    when = when or datetime.datetime.now()
    base = os.path.splitext(os.path.basename(source_file or "data"))[0] or "data"
    return os.path.join(output_dir, when.strftime("%Y%m%d"), base + ".xlsx")


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
