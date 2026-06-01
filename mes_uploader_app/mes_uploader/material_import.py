# -*- coding: utf-8 -*-
"""Nhập danh sách mã liệu từ file Excel/CSV.

File mã liệu gồm cột tên + các cột số đầu, kèm cột "Chuyên án" (tùy chọn):
    Chuyên án | Tên mã liệu | Số đầu 4X | Số đầu 8X | Số đầu 16X
Cột số đầu nào không có thì bỏ trống (mặc định 0) — một mã có thể chỉ
dùng 1 vài loại đầu. Cột Chuyên án dùng để gom nhóm mã liệu; bỏ trống thì
mã liệu thuộc nhóm chung.

- Tự nhận diện CSV hay XLSX theo *nội dung* (dùng chung bộ đọc của
  ``data_reader`` — không dựa vào đuôi file).
- Tự nhận dòng tiêu đề (header) nếu có; nếu không có thì đọc theo thứ tự
  cột cũ (cột 1 = tên, cột 2 = số đầu 8X, cột 3 = số đầu 16X). Muốn nhập
  cột 4X thì cần có dòng tiêu đề.
- Bỏ qua dòng trống / dòng không có tên mã liệu.

Module này KHÔNG phụ thuộc Qt nên có thể kiểm thử headless.
"""

import unicodedata

from .config import MaterialConfig
from .data_reader import _read_rows


# Từ khóa nhận diện cột "tên mã liệu" (đã bỏ dấu + bỏ khoảng trắng, chữ thường)
_NAME_KEYS = ("ten", "ma", "lieu", "name", "code")
# Từ khóa nhận diện cột "chuyên án" (project) — xét trước cột tên
_PROJECT_KEYS = ("chuyen", "duan", "project", "case")


def _norm(value):
    """Chuẩn hóa chuỗi để so khớp tiêu đề: bỏ dấu tiếng Việt, bỏ khoảng
    trắng, đưa về chữ thường. Ví dụ 'Số đầu 16X' -> 'sodau16x'."""
    text = str(value).strip().lower().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return "".join(text.split())


def _detect_columns(header):
    """Dò vị trí các cột từ dòng tiêu đề.

    Trả về (idx_name, idx_proj, idx_4x, idx_8x, idx_16x) nếu nhận ra đây là
    dòng tiêu đề (có cột tên + ít nhất 1 cột số đầu); cột nào không có = None.
    Cột "Chuyên án" (project) là tùy chọn. Ngược lại trả về None.
    """
    idx_name = idx_proj = idx_4x = idx_8x = idx_16x = None
    for i, cell in enumerate(header):
        h = _norm(cell)
        if not h:
            continue
        if "16" in h:                       # xét 16 trước 8/4 (tránh nuốt nhầm)
            idx_16x = i
        elif "8" in h:
            idx_8x = i
        elif "4" in h:
            idx_4x = i
        elif any(k in h for k in _PROJECT_KEYS):   # chuyên án xét trước cột tên
            idx_proj = i
        elif any(k in h for k in _NAME_KEYS):
            idx_name = i
    if idx_name is not None and (idx_4x is not None or idx_8x is not None
                                 or idx_16x is not None):
        return idx_name, idx_proj, idx_4x, idx_8x, idx_16x
    return None


def _cell_int(row, idx):
    """Lấy ô số nguyên an toàn (chấp nhận '2', '2.0', 2.0 -> 2)."""
    if idx is None or idx >= len(row):
        return 0
    try:
        return int(float(str(row[idx]).strip()))
    except (TypeError, ValueError):
        return 0


def parse_materials(path):
    """Đọc file Excel/CSV -> (danh_sách_MaterialConfig, số_dòng_bỏ_qua).

    Ném IOError nếu không đọc được file.
    """
    rows = [r for r in _read_rows(path)
            if r and any(str(c).strip() for c in r)]
    if not rows:
        return [], 0

    cols = _detect_columns(rows[0])
    if cols is not None:
        idx_name, idx_proj, idx_4x, idx_8x, idx_16x = cols
        data_rows = rows[1:]
    else:                                   # không có tiêu đề -> theo thứ tự cột cũ
        idx_name, idx_proj, idx_4x, idx_8x, idx_16x = 0, None, None, 1, 2
        data_rows = rows

    materials, skipped = [], 0
    for r in data_rows:
        name = str(r[idx_name]).strip() if idx_name < len(r) else ""
        if not name:
            skipped += 1
            continue
        project = (str(r[idx_proj]).strip()
                   if idx_proj is not None and idx_proj < len(r) else "")
        materials.append(MaterialConfig(
            name=name,
            project=project,
            heads_4x=_cell_int(r, idx_4x),
            heads_8x=_cell_int(r, idx_8x),
            heads_16x=_cell_int(r, idx_16x)))
    return materials, skipped
