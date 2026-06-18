# -*- coding: utf-8 -*-
"""Kiểm thử nhanh data_reader + mes_api với dữ liệu mẫu (không cần phần cứng).

Chạy:  python -m tests.test_data_reader
"""

import datetime
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl

from mes_uploader import data_reader, mes_api
from mes_uploader.config import PathConfig, SideConfig


def main():
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "sample_data")
    paths = PathConfig(base_dir=base)
    paths.xlsx_only = False
    left = SideConfig(name="LEFT", ccd_prefix="CCD1")
    right = SideConfig(name="RIGHT", ccd_prefix="CCD2")

    # Dữ liệu mẫu cố định ở ngày cũ (20260523/28) nên dùng require_today=False.
    print("== File mới nhất mỗi bên (8X) ==")
    for side in (left, right):
        r = data_reader.get_latest_for_side(paths, side, "8X", require_today=False)
        print("  %-5s %s" % (side.ccd_prefix, os.path.relpath(r["file"], base)))
        print("        time=%s judge=%s  #values=%d  values[:3]=%s"
              % (r["time"], r["judge"], len(r["values"]), r["values"][:3]))
        assert r["judge"] in ("OK", "NG"), "Judge phải là OK/NG"
        assert len(r["values"]) > 0, "Phải có giá trị đo"

    # Đọc file XLSX-đội-lốt-.csv (tự nhận diện theo nội dung)
    print("\n== Tự nhận diện XLSX mang đuôi .csv ==")
    xlsx_path = os.path.join(base, "8X/data/20260523/CCD1_NearStack.csv")
    r = data_reader.read_latest_measurement(xlsx_path)
    print("  time=%s judge=%s #values=%d" % (r["time"], r["judge"], len(r["values"])))
    assert len(r["values"]) > 100

    # Gộp 2 đầu 8X -> 1 payload {sn, stationName, empNo, timer}
    print("\n== build_payload (2 đầu) ==")
    r1 = data_reader.get_latest_for_side(paths, left, "8X", require_today=False)
    r2 = data_reader.get_latest_for_side(paths, left, "8X", require_today=False)
    payload = mes_api.build_payload("SN123456", [r1, r2], result="PASS",
                                    station_name="STATION-8X", emp_no="V3081479")
    n1 = len(r1["values"])
    print("  sn=%s stationName=%s empNo=%s"
          % (payload["sn"], payload["stationName"], payload["empNo"]))
    print("  timer[:60]=%s…" % payload["timer"][:60])
    assert payload["sn"] == "SN123456"
    assert payload["stationName"] == "STATION-8X"
    assert payload["empNo"] == "V3081479"
    # payload gồm đúng 5 trường theo yêu cầu MES (có thêm 'result')
    assert set(payload) == {"sn", "stationName", "result", "empNo", "timer"}
    # timer: mỗi đầu 1 nhóm "L<M>:v1-v2-...-vN", các nhóm cách nhau "; "
    timer = payload["timer"]
    blocks = timer.split("; ")
    assert len(blocks) == 2, "2 đầu -> 2 nhóm L1/L2"
    assert blocks[0].startswith("L1:") and blocks[1].startswith("L2:")
    vals1 = blocks[0][len("L1:"):].split("-")
    vals2 = blocks[1][len("L2:"):].split("-")
    assert len(vals1) == n1 and len(vals2) == n1   # đủ số giá trị mỗi đầu
    # giá trị đầu/cuối khớp dữ liệu đọc được
    assert vals1[0] == mes_api._fmt_value(r1["values"][0])
    assert vals1[-1] == mes_api._fmt_value(r1["values"][-1])

    # stationName / empNo mặc định rỗng khi không truyền
    print("\n== build_payload mặc định (không truyền stationName/empNo) ==")
    p2 = mes_api.build_payload("SN1", [r1], result="PASS")
    assert p2["stationName"] == "" and p2["empNo"] == ""
    print("  OK")

    # CHỈ đọc .xlsx: thư mục có cả CCD1_*.csv (giá trị 111) lẫn .xlsx (222)
    print("\n== xlsx_only: bỏ .csv, chỉ đọc .xlsx ==")
    root = tempfile.mkdtemp(prefix="xlsxonly_")
    day = datetime.datetime.now().strftime("%Y%m%d")
    d = os.path.join(root, "8X", "data", day)
    os.makedirs(d, exist_ok=True)
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Time", "Judge", "IspTime", "Data01"]); ws.append(["t", "OK", 1, 222.0])
    wb.save(os.path.join(d, "CCD1_NearStack.xlsx")); wb.close()
    with open(os.path.join(d, "CCD1_NearStack.csv"), "w", encoding="utf-8") as f:
        f.write("Time,Judge,IspTime,Data01\nt,NG,1,111.0\n")   # .csv MỚI hơn, phải bỏ
    p = PathConfig(base_dir=root)                               # mặc định xlsx_only=True
    r = data_reader.get_latest_for_side(p, left, "8X", require_today=False)
    assert r["values"] == [222.0] and r["judge"] == "OK", r     # = .xlsx, KHÔNG phải .csv
    p.xlsx_only = False                                        # cho phép .csv -> lấy mới nhất
    r2 = data_reader.get_latest_for_side(p, left, "8X", require_today=False)
    assert r2["values"] == [111.0], r2                          # = .csv (mới hơn)
    print("  xlsx_only=True -> .xlsx(222) | False -> .csv(111)  ✔")

    # Ưu tiên .xlsx, thiếu thì .csv: thư mục CHỈ có .csv
    print("\n== xlsx_fallback_csv: thiếu .xlsx -> lùi về .csv ==")
    root2 = tempfile.mkdtemp(prefix="xlsxfb_")
    d2 = os.path.join(root2, "8X", "data", day)
    os.makedirs(d2, exist_ok=True)
    with open(os.path.join(d2, "CCD1_NearStack.csv"), "w", encoding="utf-8") as f:
        f.write("Time,Judge,IspTime,Data01\nt,OK,1,333.0\n")
    pf = PathConfig(base_dir=root2)                             # xlsx_only=True, no fallback
    try:
        data_reader.get_latest_for_side(pf, left, "8X", require_today=False)
        assert False, "chỉ .xlsx mà không có -> phải báo lỗi"
    except data_reader.DataNotAvailableError:
        pass
    pf.xlsx_fallback_csv = True                                 # bật lùi về .csv
    r3 = data_reader.get_latest_for_side(pf, left, "8X", require_today=False)
    assert r3["values"] == [333.0], r3                          # đọc được .csv
    print("  thiếu .xlsx: no-fallback -> lỗi | fallback -> .csv(333)  ✔")

    print("\nTAT CA TEST PASS ✔")


if __name__ == "__main__":
    main()
