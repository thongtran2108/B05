# -*- coding: utf-8 -*-
"""Kiểm thử lưu giá trị đo ra Excel (.xlsx) kèm cột SN.

- append_reading: tạo file + header [SN, Time, Judge, IspTime, Data01..N] rồi
  thêm 1 dòng mỗi lần đọc; gọi nhiều lần -> nhiều dòng (đúng SN tương ứng).
- output_path: <dir>/<YYYYMMDD>/<tên file đo gốc>.xlsx.
- Worker (giả lập, 2 đầu 8X) bật Excel -> tạo file có cột SN, ≥ 2 dòng.

Chạy:  python -m tests.test_excel_export
"""

import datetime
import glob
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl

from mes_uploader import excel_export as xe, mes_api
from mes_uploader.config import AppConfig, MaterialConfig, PathConfig
from mes_uploader.core.side_worker import SideWorker
from mes_uploader.hardware.plc_client import MockPlcClient


def _rows(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    out = [[c for c in r] for r in ws.iter_rows(values_only=True)]
    wb.close()
    return ws.title, out


def main():
    root = tempfile.mkdtemp(prefix="xl_test_")
    when = datetime.datetime(2026, 6, 9, 10, 18, 33)

    # 1) output_path: theo ngày + tên file đo gốc
    print("== output_path ==")
    op = xe.output_path(root, "/data/20260609/CCD1_NearStack.csv", when=when)
    assert op == os.path.join(root, "20260609", "CCD1_NearStack.xlsx"), op

    # 2) append_reading: header có cột SN + ghi đúng giá trị, mỗi lần 1 dòng
    print("\n== append_reading (2 dòng, 2 SN) ==")
    r1 = {"time": "10:18:33", "judge": "OK", "isp_time": 1975,
          "values": [24.24, 23.64, 22.0], "headers": ["Data01", "Data02", "Data03"]}
    r2 = {"time": "10:18:40", "judge": "NG", "isp_time": 1949,
          "values": [24.10, 23.50, 21.9], "headers": ["Data01", "Data02", "Data03"]}
    xe.append_reading(op, "SN-001", r1)
    xe.append_reading(op, "SN-002", r2)

    title, rows = _rows(op)
    assert title == "Data", title
    assert rows[0] == ["SN", "Time", "Judge", "IspTime", "Data01", "Data02", "Data03"], rows[0]
    assert rows[1] == ["SN-001", "10:18:33", "OK", 1975, 24.24, 23.64, 22.0], rows[1]
    assert rows[2] == ["SN-002", "10:18:40", "NG", 1949, 24.10, 23.50, 21.9], rows[2]
    assert len(rows) == 3, "1 header + 2 dòng dữ liệu"
    print("  header:", rows[0])
    print("  row1  :", rows[1])

    # 3) Worker giả lập (2 đầu 8X) bật Excel -> file có cột SN, ≥ 2 dòng
    print("\n== worker -> file Excel có cột SN ==")
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "sample_data")
    out_dir = os.path.join(root, "wk")
    cfg = AppConfig()
    cfg.simulation = True
    cfg.poll_interval_ms = 20
    cfg.paths = PathConfig(base_dir=base)
    cfg.paths.require_today = False
    cfg.materials = [MaterialConfig("ABC", heads_8x=2)]
    cfg.api.api_8x.url = "http://mes/8x/upload"
    cfg.excel.enabled = True
    cfg.excel.output_dir = out_dir
    mes_api.post_payload = lambda u, p, **k: (True, 200, "OK")

    w = SideWorker("left", cfg, MockPlcClient(), lambda et, **d: None)
    w.start()
    w.arm(cfg.materials[0], "8X")
    time.sleep(0.1)
    w.submit_sn("SN-WK-7")
    time.sleep(0.2)
    for _ in range(2):
        w.simulate_trigger()
        time.sleep(0.3)
    time.sleep(0.5)
    w.stop()

    files = glob.glob(os.path.join(out_dir, "**", "*.xlsx"), recursive=True)
    assert files, "Phải tạo file Excel"
    print("  file:", os.path.relpath(files[0], out_dir))
    _t, wrows = _rows(files[0])
    assert wrows[0][0] == "SN", wrows[0]
    data_rows = [r for r in wrows[1:] if r and r[0]]
    assert len(data_rows) == 2, "2 đầu -> 2 dòng, thực tế %d" % len(data_rows)
    assert all(r[0] == "SN-WK-7" for r in data_rows), data_rows
    print("  số dòng dữ liệu:", len(data_rows), "| SN:", data_rows[0][0])

    # 4) Tắt -> không tạo file
    print("\n== tắt Excel -> không tạo file ==")
    out2 = os.path.join(root, "off")
    cfg.excel.enabled = False
    cfg.excel.output_dir = out2
    w = SideWorker("left", cfg, MockPlcClient(), lambda et, **d: None)
    w.start(); w.arm(cfg.materials[0], "8X"); time.sleep(0.1)
    w.submit_sn("SN-OFF"); time.sleep(0.2)
    for _ in range(2):
        w.simulate_trigger(); time.sleep(0.3)
    time.sleep(0.3); w.stop()
    assert glob.glob(os.path.join(out2, "**", "*.xlsx"), recursive=True) == []

    print("\nTEST EXCEL-EXPORT PASS ✔")


if __name__ == "__main__":
    main()
