# -*- coding: utf-8 -*-
"""Worker CHỜ tới khi có DÒNG MỚI rồi mới đọc — sửa lỗi 'lấy trước 1 cái'.

- Máy ghi dòng mới TRỄ: worker chờ (báo 'acquiring') rồi đọc ĐÚNG dòng mới.
- Quá thời gian chờ mà chưa có dòng mới: HỦY + cảnh báo (KHÔNG dùng dữ liệu cũ).

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
    events = []
    on_event = lambda et, **d2: events.append((et, d2))

    # --- 1) Máy ghi dòng mới TRỄ: worker chờ ('acquiring') rồi đọc đúng dòng mới ---
    print("== chờ dòng mới (máy ghi trễ) + báo ĐANG LẤY DỮ LIỆU ==")
    cfg = _make_cfg(root, delay_ms=3000)               # chờ tối đa 3s
    w = SideWorker("left", cfg, MockPlcClient(), on_event)
    w.start(); w.arm(cfg.materials[0], "8X"); time.sleep(0.1)
    w.submit_sn("SN-WAIT"); time.sleep(0.3)            # _begin_sn chốt mốc = dòng cũ
    w.simulate_trigger()                               # tín hiệu tới khi CHƯA có dòng mới

    def _late_write():
        time.sleep(0.6)
        with open(csv, "a", encoding="utf-8") as f:
            f.write("09:10:00,NG,500,77.0,77.0\n")
    threading.Thread(target=_late_write, daemon=True).start()
    time.sleep(1.6)
    w.stop()

    assert any(et == "acquiring" for et, _ in events), "phải báo 'acquiring' khi chờ"
    reads = [d2 for et, d2 in events if et == "reading"]
    assert reads, "phải đọc được dòng mới"
    assert reads[-1]["judge"] == "NG" and list(reads[-1]["values"]) == [77.0, 77.0], reads[-1]
    print("  có 'acquiring' + đọc đúng DÒNG MỚI (NG, 77)  ✔")

    # --- 2) Quá thời gian không có dòng mới -> HỦY + cảnh báo (không dùng dòng cũ) ---
    print("\n== quá thời gian không có dòng mới -> HỦY, KHÔNG dùng dòng cũ ==")
    events.clear()
    cfg2 = _make_cfg(root, delay_ms=400)               # chờ ngắn, KHÔNG ghi thêm
    w2 = SideWorker("left", cfg2, MockPlcClient(), on_event)
    w2.start(); w2.arm(cfg2.materials[0], "8X"); time.sleep(0.1)
    w2.submit_sn("SN-NONEW"); time.sleep(0.3)
    w2.simulate_trigger()
    time.sleep(1.0)
    w2.stop()
    assert any(et == "error" for et, _ in events), "quá giờ phải BÁO LỖI (hủy)"
    assert not any(et == "reading" for et, _ in events), "KHÔNG được dùng dòng cũ"
    print("  quá 400ms -> error (hủy), không có 'reading' dòng cũ  ✔")

    # --- 3) File đang GHI DỞ (thay đổi liên tục) -> đợi ỔN ĐỊNH rồi đọc dòng CUỐI ---
    print("\n== đợi máy ghi xong (file thay đổi liên tục) rồi mới đọc ==")
    with open(csv, "w", encoding="utf-8") as f:        # reset: 1 dòng cũ
        f.write(HDR + "08:00:00,OK,500,1.0,1.0\n")
    events.clear()
    cfg3 = _make_cfg(root, delay_ms=5000)
    w3 = SideWorker("left", cfg3, MockPlcClient(), on_event)
    w3.start(); w3.arm(cfg3.materials[0], "8X"); time.sleep(0.1)
    w3.submit_sn("SN-SETTLE"); time.sleep(0.3)
    w3.simulate_trigger()

    def _busy_write():                                 # ghi liên tục 6 lần (mỗi 0.1s)
        rows = [("NG", 10), ("NG", 20), ("NG", 30),
                ("NG", 40), ("NG", 50), ("OK", 99)]    # dòng CUỐI = OK,99
        for i, (j, v) in enumerate(rows):
            time.sleep(0.1)
            with open(csv, "a", encoding="utf-8") as f:
                f.write("09:%02d:00,%s,500,%d.0,%d.0\n" % (i, j, v, v))
    threading.Thread(target=_busy_write, daemon=True).start()
    time.sleep(2.0)                                    # đủ để ghi xong + ổn định + đọc
    w3.stop()
    reads3 = [d2 for et, d2 in events if et == "reading"]
    assert reads3, "phải đọc sau khi máy ghi xong"
    # chỉ đọc khi đã ổn định -> lấy DÒNG CUỐI (OK,99), không lấy dòng giữa chừng
    assert reads3[-1]["judge"] == "OK" and list(reads3[-1]["values"]) == [99.0, 99.0], reads3[-1]
    assert all(r["values"] != [10.0, 10.0] for r in reads3), "không được đọc dòng giữa chừng"
    print("  đợi ổn định -> đọc dòng cuối (OK,99), bỏ dòng ghi dở  ✔")

    print("\nTEST WAIT-NEW-ROW PASS ✔")


if __name__ == "__main__":
    main()
