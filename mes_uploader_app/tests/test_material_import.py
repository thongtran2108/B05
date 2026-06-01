# -*- coding: utf-8 -*-
"""Kiểm thử nhập mã liệu từ Excel/CSV (không cần Qt / phần cứng).

Chạy:  python -m tests.test_material_import
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader.material_import import parse_materials, _detect_columns, _norm


def _write_xlsx(rows):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    wb.save(path)
    return path


def _write_csv(text):
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", encoding="utf-8-sig") as f:
        f.write(text)
    return path


def main():
    # 1) XLSX có tiêu đề tiếng Việt (kể cả dấu) + dòng trống xen giữa
    print("== XLSX có tiêu đề tiếng Việt ==")
    path = _write_xlsx([
        ["Tên mã liệu", "Số đầu 8X", "Số đầu 16X"],
        ["ABC", 2, 1],
        ["", "", ""],                       # dòng trống -> bỏ qua (không tính skip)
        ["BCD", 4, 0],
        ["XYZ", "", 3],                     # thiếu 8X -> mặc định 0
    ])
    mats, skipped = parse_materials(path)
    os.remove(path)
    print("  %s  (skipped=%d)" % ([(m.name, m.heads_8x, m.heads_16x) for m in mats],
                                  skipped))
    assert [m.name for m in mats] == ["ABC", "BCD", "XYZ"]
    assert (mats[0].heads_8x, mats[0].heads_16x) == (2, 1)
    assert (mats[1].heads_8x, mats[1].heads_16x) == (4, 0)
    assert (mats[2].heads_8x, mats[2].heads_16x) == (0, 3)
    assert skipped == 0

    # 2) Thứ tự cột đảo + giá trị số dạng "2.0"
    print("\n== Tiêu đề đảo cột + số kiểu '2.0' ==")
    path = _write_xlsx([
        ["heads_16x", "name", "heads_8x"],
        [1, "ABC", "2.0"],
    ])
    mats, _ = parse_materials(path)
    os.remove(path)
    print("  %s" % [(m.name, m.heads_8x, m.heads_16x) for m in mats])
    assert (mats[0].name, mats[0].heads_8x, mats[0].heads_16x) == ("ABC", 2, 1)

    # 3) CSV KHÔNG tiêu đề -> đọc theo thứ tự cột; dòng thiếu tên -> skip
    print("\n== CSV không tiêu đề (đọc theo thứ tự cột) ==")
    path = _write_csv("ABC,2,1\nBCD,4,0\n,9,9\n")
    mats, skipped = parse_materials(path)
    os.remove(path)
    print("  %s  (skipped=%d)" % ([(m.name, m.heads_8x, m.heads_16x) for m in mats],
                                  skipped))
    assert [m.name for m in mats] == ["ABC", "BCD"]
    assert skipped == 1

    # 4) Đơn vị kiểm tra hàm phụ
    #    _detect_columns trả về (idx_name, idx_proj, idx_4x, idx_8x, idx_16x)
    print("\n== _norm + _detect_columns ==")
    assert _norm("Số đầu 16X") == "sodau16x"
    assert _norm("Số đầu 4X") == "sodau4x"
    assert _norm("Tên mã liệu") == "tenmalieu"
    assert _norm("Chuyên án") == "chuyenan"
    # không có cột 4X / chuyên án -> idx = None
    assert _detect_columns(
        ["Tên mã liệu", "Số đầu 8X", "Số đầu 16X"]) == (0, None, None, 1, 2)
    # đủ 3 loại đầu
    assert _detect_columns(
        ["Tên mã liệu", "Số đầu 4X", "Số đầu 8X", "Số đầu 16X"]) == (0, None, 1, 2, 3)
    # chỉ có cột 4X
    assert _detect_columns(["Tên mã liệu", "Số đầu 4X"]) == (0, None, 1, None, None)
    # có cột Chuyên án
    assert _detect_columns(
        ["Chuyên án", "Tên mã liệu", "Số đầu 4X", "Số đầu 8X", "Số đầu 16X"]
    ) == (1, 0, 2, 3, 4)
    assert _detect_columns(["ABC", "2", "1"]) is None   # không phải tiêu đề
    print("  OK")

    # 5) File có cột 4X: nhận đủ 3 loại đầu + mã chỉ có đầu 4X
    print("\n== Cột 4X (4X/8X/16X) + mã chỉ có 4X ==")
    path = _write_xlsx([
        ["Tên mã liệu", "Số đầu 4X", "Số đầu 8X", "Số đầu 16X"],
        ["ABC", 5, 2, 1],
        ["DEF", 3, 0, 0],                   # chỉ có đầu 4X
    ])
    mats, _ = parse_materials(path)
    os.remove(path)
    print("  %s" % [(m.name, m.heads_4x, m.heads_8x, m.heads_16x) for m in mats])
    assert (mats[0].heads_4x, mats[0].heads_8x, mats[0].heads_16x) == (5, 2, 1)
    assert (mats[1].heads_4x, mats[1].heads_8x, mats[1].heads_16x) == (3, 0, 0)
    assert all(m.project == "" for m in mats)   # không có cột chuyên án -> rỗng

    # 6) Cột Chuyên án: gom mã liệu theo chuyên án riêng
    print("\n== Cột Chuyên án (mỗi chuyên án có mã liệu riêng) ==")
    path = _write_xlsx([
        ["Chuyên án", "Tên mã liệu", "Số đầu 4X", "Số đầu 8X", "Số đầu 16X"],
        ["CA-A", "ABC", 0, 2, 1],
        ["CA-A", "BCD", 0, 4, 0],
        ["CA-B", "DEF", 3, 0, 0],           # chuyên án khác, mã liệu riêng
    ])
    mats, _ = parse_materials(path)
    os.remove(path)
    print("  %s" % [(m.project, m.name) for m in mats])
    assert [(m.project, m.name) for m in mats] == [
        ("CA-A", "ABC"), ("CA-A", "BCD"), ("CA-B", "DEF")]
    assert (mats[2].heads_4x, mats[2].heads_8x, mats[2].heads_16x) == (3, 0, 0)

    print("\nTAT CA TEST PASS ✔")


if __name__ == "__main__":
    main()
