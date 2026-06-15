# -*- coding: utf-8 -*-
"""CHỈ đọc .xlsx + mỗi tín hiệu đọc DÒNG MỚI NHẤT -> 2 đầu không trùng dữ liệu/ảnh.

Trong thư mục ngày có CẢ <tên>.csv (cũ, nhiễu) và <tên>.xlsx (máy cập nhật).
Theo yêu cầu: CHỈ đọc .xlsx; mỗi lần nhận tín hiệu PLC đọc lại file -> dòng mới
nhất. Máy ghi thêm 1 dòng + 1 ảnh cho mỗi đầu giữa 2 tín hiệu:
  - đầu #1 đo NG, đầu #2 đo OK.
Kỳ vọng:
  - data 2 đầu KHÁC nhau (NG rồi OK), KHÔNG lấy nhầm số từ file .csv.
  - Excel có 2 dòng (NG, OK); ảnh: #1 _Left_Failed, #2 _Left_Passed.
  - result POST = FAIL (1 đầu NG là FAIL).

Chạy:  python -m tests.test_multi_head_distinct
"""

import datetime
import glob
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl
from PIL import Image

from mes_uploader import mes_api
from mes_uploader.config import AppConfig, MaterialConfig, PathConfig
from mes_uploader.core.side_worker import SideWorker
from mes_uploader.hardware.plc_client import MockPlcClient

HEADER = ["Time", "Judge", "IspTime", "Data01", "Data02"]


def _new_xlsx(path, *rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HEADER)
    for r in rows:
        ws.append(r)
    wb.save(path)
    wb.close()


def _append_xlsx(path, row):
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    ws.append(row)
    wb.save(path)
    wb.close()


def _mkjpg(path, size):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new("RGB", size, (20, 90, 160)).save(path, "JPEG")


def main():
    root = tempfile.mkdtemp(prefix="multi_head_")
    day = datetime.datetime.now().strftime("%Y%m%d")
    data_dir = os.path.join(root, "8X", "data", day)
    os.makedirs(data_dir, exist_ok=True)

    # .xlsx = file máy cập nhật (đọc cái này); header + 1 dòng CŨ (SN trước).
    xlsx = os.path.join(data_dir, "CCD1_NearStack.xlsx")
    _new_xlsx(xlsx, ["09:00:00", "OK", 500, 1.0, 1.0])
    # .csv = file CŨ/NHIỄU cùng tên, để MỚI hơn (mtime) — phải bị BỎ QUA.
    with open(os.path.join(data_dir, "CCD1_NearStack.csv"), "w", encoding="utf-8") as f:
        f.write(",".join(HEADER) + "\n")
        f.write("23:59:59,NG,999,999.0,999.0\n")   # số 999 KHÔNG được xuất hiện

    img_src = os.path.join(root, "src8x")
    img_up = os.path.join(root, "up8x")
    xl_dir = os.path.join(root, "xl8x")

    cfg = AppConfig()
    cfg.simulation = True
    cfg.poll_interval_ms = 20
    cfg.paths = PathConfig(base_dir=root)
    cfg.paths.require_today = False
    # KHÔNG đặt xlsx_only -> dùng mặc định True (chỉ đọc .xlsx)
    cfg.materials = [MaterialConfig("ABC", heads_8x=2)]
    cfg.api.api_8x.url = "http://mes/8x/upload"
    cfg.images.enabled = True
    cfg.images.img_8x.source_dir = img_src
    cfg.images.img_8x.upload_dir = img_up
    cfg.excel.enabled = True
    cfg.excel.output_dir_8x = xl_dir

    payloads = []
    mes_api.post_payload = lambda url, payload, **kw: (payloads.append(payload),
                                                       (True, 200, "OK"))[1]
    readings = []

    def on_event(et, **d):
        if et == "reading":
            readings.append(d)

    w = SideWorker("left", cfg, MockPlcClient(), on_event)
    w.start()
    w.arm(cfg.materials[0], "8X")
    time.sleep(0.1)
    w.submit_sn("SN-MH-9")
    time.sleep(0.2)

    # đầu #1: máy ghi thêm dòng NG (vào .xlsx) + ảnh NG, rồi báo tín hiệu
    _append_xlsx(xlsx, ["09:10:00", "NG", 500, 10.0, 11.0])
    _mkjpg(os.path.join(img_src, "Image", day, "CCD1", "NG", "h1.jpg"), (11, 11))
    w.simulate_trigger()
    time.sleep(0.4)

    # đầu #2: máy ghi thêm dòng OK + ảnh OK, rồi báo tín hiệu
    _append_xlsx(xlsx, ["09:11:00", "OK", 500, 20.0, 21.0])
    _mkjpg(os.path.join(img_src, "Image", day, "CCD1", "OK", "h2.jpg"), (22, 22))
    w.simulate_trigger()
    time.sleep(0.6)
    w.stop()

    # 1) DATA: đầu#1 = NG (10,11), đầu#2 = OK (20,21); KHÔNG lẫn số 999 của .csv
    print("== chỉ đọc .xlsx + dòng mới nhất mỗi tín hiệu ==")
    r = {d["index"]: d for d in readings}
    assert set(r) == {1, 2}, "phải có 2 đầu, nhận: %r" % sorted(r)
    assert r[1]["judge"] == "NG" and list(r[1]["values"]) == [10.0, 11.0], r[1]
    assert r[2]["judge"] == "OK" and list(r[2]["values"]) == [20.0, 21.0], r[2]
    assert all(999.0 not in list(d["values"]) for d in readings), "đã đọc nhầm .csv!"
    print("  đầu#1 NG (10,11) | đầu#2 OK (20,21) | .csv (999) bị bỏ qua  ✔")

    # 2) result POST = FAIL (1 đầu NG)
    assert payloads and payloads[-1]["result"] == "FAIL", payloads[-1:]
    print("  result=FAIL  ✔")

    # 3) EXCEL: 2 dòng KHÁC nhau (NG rồi OK), tên file CCD1->Left
    xls = glob.glob(os.path.join(xl_dir, "**", "*.xlsx"), recursive=True)
    assert xls and os.path.basename(xls[0]).startswith("Left_"), xls
    wb = openpyxl.load_workbook(xls[0]); ws = wb.active
    try:
        body = [(ws.cell(rr, 1).value, ws.cell(rr, 3).value)
                for rr in range(2, ws.max_row + 1) if ws.cell(rr, 1).value]
        assert [j for _, j in body] == ["NG", "OK"], body
        assert all(sn == "SN-MH-9" for sn, _ in body), body
        print("  Excel %s: 2 dòng NG rồi OK  ✔" % os.path.basename(xls[0]))
    finally:
        wb.close()

    # 4) ẢNH: #1 _Left_Failed (NG, 11x11) | #2 _Left_Passed (OK, 22x22)
    names = sorted(fn for _d, _s, fns in os.walk(img_up) for fn in fns)
    assert len(names) == 2, names
    f1 = [n for n in names if "_Left_Failed_#1" in n]
    p2 = [n for n in names if "_Left_Passed_#2" in n]
    assert f1 and p2, names
    with Image.open(os.path.join(img_up, day, f1[0])) as im:
        assert im.size == (11, 11), im.size
    with Image.open(os.path.join(img_up, day, p2[0])) as im:
        assert im.size == (22, 22), im.size
    print("  ảnh #1=%s | #2=%s  ✔" % (f1[0], p2[0]))

    print("\nTEST MULTI-HEAD-DISTINCT (xlsx + latest) PASS ✔")


if __name__ == "__main__":
    main()
