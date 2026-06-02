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

    # Gộp 2 đầu 8X -> 1 payload
    print("\n== build_payload (2 đầu, values_only) ==")
    r1 = data_reader.get_latest_for_side(paths, left, "8X", require_today=False)
    r2 = data_reader.get_latest_for_side(paths, left, "8X", require_today=False)
    payload = mes_api.build_payload("SN123456", [r1, r2], data_format="values_only")
    print("  sn=%s result=%s  so_dau=%d  so_value_dau1=%d"
          % (payload["sn"], payload["result"], len(payload["data"]),
             len(payload["data"][0])))
    assert payload["sn"] == "SN123456"
    assert payload["result"] in ("OK", "NG")
    assert len(payload["data"]) == 2
    # 3 trường mới: mặc định rỗng khi không truyền
    assert payload["project"] == "" and payload["material"] == ""
    assert payload["measuring_head"] == ""

    # build_payload có chuyên án / mã liệu / loại đầu đo
    print("\n== build_payload kèm project/material/measuring_head ==")
    p2 = mes_api.build_payload("SN1", [r1], project="Chuyên án A",
                               material="ABC", measuring_head="16X")
    print("  project=%s material=%s measuring_head=%s"
          % (p2["project"], p2["material"], p2["measuring_head"]))
    assert (p2["project"], p2["material"], p2["measuring_head"]) == (
        "Chuyên án A", "ABC", "16X")

    print("\nTAT CA TEST PASS ✔")


if __name__ == "__main__":
    main()
