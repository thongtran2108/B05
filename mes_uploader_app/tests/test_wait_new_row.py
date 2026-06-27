# -*- coding: utf-8 -*-
"""Worker CHỜ tới khi có DÒNG MỚI rồi mới đọc — sửa lỗi 'lấy trước 1 cái' khi máy
ghi file TRỄ hơn tín hiệu PLC.

Kịch bản: nhận tín hiệu trong khi file CHƯA có dòng mới (chỉ có dòng cũ). Một lúc
sau máy mới ghi dòng mới. Worker (trigger_delay_ms = thời gian chờ TỐI ĐA) phải
đợi dòng mới rồi đọc ĐÚNG nó, KHÔNG lấy dòng cũ.

Chạy:  python -m tests.test_wait_new_row
"""

import datetime
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader import mes_api
from mes_uploader.config import AppConfig, MaterialConfig, PathConfig
from mes_uploader.core.side_worker import SideWorker
from mes_uploader.hardware.plc_client import MockPlcClient

HDR = "Time,Judge,IspTime,Data01,Data02\n"


def _make_cfg(root, delay_ms):
    cfg = AppConfig()
    cfg.simulation = True
    cfg.poll_interval_ms = 20
    cfg.paths = PathConfig(base_dir=root)
    cfg.paths.require_today = False
    cfg.paths.xlsx_only = False
    cfg.trigger_delay_ms = delay_ms
    cfg.materials = [MaterialConfig("ABC", heads_8x=1)]
    cfg.api.api_8x.url = "http://mes/8x/upload"
    return cfg


def main():
    root = tempfile.mkdtemp(prefix="wait_new_")
    day = datetime.datetime.now().strftime("%Y%m%d")
    d = os.path.join(root, "8X", "data", day)
    os.makedirs(d, exist_ok=True)
    csv = os.path.join(d, "CCD1_NearStack.csv")
    with open(csv, "w", encoding="utf-8") as f:        # chỉ có DÒNG CŨ lúc đầu
        f.write(HDR + "09:00:00,OK,500,1.0,1.0\n")

    mes_api.post_payload = lambda url, payload, **kw: (True, 200, "OK")
    readings = []
    on_event = lambda et, **d2: readings.append(d2) if et == "reading" else None

    # --- 1) Máy ghi dòng mới TRỄ: worker phải chờ rồi đọc đúng dòng mới ---
    print("== chờ dòng mới (máy ghi trễ) ==")
    cfg = _make_cfg(root, delay_ms=3000)               # chờ tối đa 3s
    w = SideWorker("left", cfg, MockPlcClient(), on_event)
    w.start()
    w.arm(cfg.materials[0], "8X")
    time.sleep(0.1)
    w.submit_sn("SN-WAIT")
    time.sleep(0.3)                                    # _begin_sn chốt mốc = dòng cũ
    w.simulate_trigger()                               # tín hiệu tới khi CHƯA có dòng mới
    # 0.5s sau máy mới ghi dòng mới (NG, 77)
    def _late_write():
        time.sleep(0.5)
        with open(csv, "a", encoding="utf-8") as f:
            f.write("09:10:00,NG,500,77.0,77.0\n")
    threading.Thread(target=_late_write, daemon=True).start()
    time.sleep(1.5)                                    # đủ để worker chờ + đọc
    w.stop()

    assert readings, "phải đọc được dòng mới"
    r = readings[-1]
    assert r["judge"] == "NG" and list(r["values"]) == [77.0, 77.0], r
    print("  đọc đúng DÒNG MỚI: judge=NG values=[77,77] (không lấy dòng cũ 1.0)  ✔")

    # --- 2) Không có dòng mới + chờ ngắn -> dùng dòng hiện có (không treo) ---
    print("\n== hết chờ, không có dòng mới -> dùng dòng hiện có (không treo) ==")
    readings.clear()
    cfg2 = _make_cfg(root, delay_ms=300)               # chờ ngắn, KHÔNG ghi thêm
    # file hiện có dòng cuối là (NG,77) từ phần trên
    w2 = SideWorker("left", cfg2, MockPlcClient(), on_event)
    w2.start()
    w2.arm(cfg2.materials[0], "8X")
    time.sleep(0.1)
    w2.submit_sn("SN-NONEW")
    time.sleep(0.3)
    w2.simulate_trigger()
    time.sleep(0.8)
    w2.stop()
    assert readings, "vẫn phải đọc (fallback dòng hiện có)"
    assert list(readings[-1]["values"]) == [77.0, 77.0], readings[-1]
    print("  hết 300ms -> dùng dòng hiện có (NG,77), không treo dây chuyền  ✔")

    print("\nTEST WAIT-NEW-ROW PASS ✔")


if __name__ == "__main__":
    main()
