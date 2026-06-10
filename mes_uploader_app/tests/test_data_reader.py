# -*- coding: utf-8 -*-
"""Kiểm thử nhanh data_reader + mes_api với dữ liệu mẫu (không cần phần cứng).

Chạy:  python -m tests.test_data_reader
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader import data_reader, mes_api
from mes_uploader.config import PathConfig, SideConfig


def main():
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "sample_data")
    paths = PathConfig(base_dir=base)
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
    payload = mes_api.build_payload("SN123456", [r1, r2],
                                    station_name="STATION-8X", emp_no="V3081479")
    n1 = len(r1["values"])
    print("  sn=%s stationName=%s empNo=%s"
          % (payload["sn"], payload["stationName"], payload["empNo"]))
    print("  timer[:60]=%s…" % payload["timer"][:60])
    assert payload["sn"] == "SN123456"
    assert payload["stationName"] == "STATION-8X"
    assert payload["empNo"] == "V3081479"
    # payload chỉ gồm đúng 4 trường theo yêu cầu MES
    assert set(payload) == {"sn", "stationName", "empNo", "timer"}
    # timer: mỗi đầu 1 nhóm "L<M>: v1 - v2 - ... - vN", các nhóm cách nhau "; "
    timer = payload["timer"]
    blocks = timer.split("; ")
    assert len(blocks) == 2, "2 đầu -> 2 nhóm L1/L2"
    assert blocks[0].startswith("L1: ") and blocks[1].startswith("L2: ")
    vals1 = blocks[0][len("L1: "):].split(" - ")
    vals2 = blocks[1][len("L2: "):].split(" - ")
    assert len(vals1) == n1 and len(vals2) == n1   # đủ số giá trị mỗi đầu
    # giá trị đầu/cuối khớp dữ liệu đọc được
    assert vals1[0] == mes_api._fmt_value(r1["values"][0])
    assert vals1[-1] == mes_api._fmt_value(r1["values"][-1])

    # stationName / empNo mặc định rỗng khi không truyền
    print("\n== build_payload mặc định (không truyền stationName/empNo) ==")
    p2 = mes_api.build_payload("SN1", [r1])
    assert p2["stationName"] == "" and p2["empNo"] == ""
    print("  OK")

    print("\nTAT CA TEST PASS ✔")


if __name__ == "__main__":
    main()
