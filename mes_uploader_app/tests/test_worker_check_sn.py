# -*- coding: utf-8 -*-
"""Worker tích hợp bước GET kiểm tra SN:

- SN bị CHẶN (GET báo không hợp lệ) -> KHÔNG vào RUNNING, KHÔNG POST,
  ở lại chờ quét mã khác.
- SN hợp lệ kế tiếp -> chạy đủ đầu -> POST (chỉ thành công khi body chứa
  chuỗi mong đợi).

Chạy:  python -m tests.test_worker_check_sn
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader import mes_api
from mes_uploader.config import AppConfig, MaterialConfig, PathConfig
from mes_uploader.hardware.plc_client import MockPlcClient
from mes_uploader.core.side_worker import SideWorker, ST_RUNNING, ST_WAIT_SCAN


def main():
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "sample_data")
    cfg = AppConfig()
    cfg.simulation = True
    cfg.poll_interval_ms = 25
    cfg.paths = PathConfig(base_dir=base)
    cfg.paths.require_today = False           # data mẫu ngày cũ
    cfg.materials = [MaterialConfig("ABC", heads_8x=1, heads_16x=1)]
    # API riêng cho đầu 8X (worker arm 8X) — kiểm tra SN + POST theo API này
    cfg.api.api_8x.check_enabled = True
    cfg.api.api_8x.check_url_prefix = "http://mes/check?sn="
    cfg.api.api_8x.check_ok_value = "0"
    cfg.api.api_8x.post_ok_contains = "200"

    # GET giả: chỉ SN 'GOOD' hợp lệ
    def fake_check(sn, prefix, suffix="", ok_value="0", **kw):
        if sn == "GOOD":
            return True, "SN hợp lệ"
        return False, "SN đã test (giả lập)"

    posted = {"n": 0}

    def fake_post(url, payload, **kw):
        posted["n"] += 1
        posted["sn"] = payload["sn"]
        return True, 200, '{"code":"200"}'

    mes_api.check_sn = fake_check
    mes_api.post_payload = fake_post

    events = []
    w = SideWorker("left", cfg, MockPlcClient(),
                   lambda et, **d: events.append((et, d)))
    w.start()
    w.arm(cfg.materials[0], "8X")
    time.sleep(0.1)

    # 1) SN xấu -> bị chặn
    w.submit_sn("BADSN")
    time.sleep(0.25)
    rejected = [d for (t, d) in events if t == "sn_rejected"]
    assert rejected and rejected[-1]["sn"] == "BADSN", "SN xấu phải bị chặn"
    assert w._state == ST_WAIT_SCAN, "SN xấu -> phải ở lại chờ quét"
    assert posted["n"] == 0, "SN xấu -> tuyệt đối không POST"
    print("1) SN xấu BADSN bị chặn, ở lại chờ quét, chưa POST ✔")

    # 2) SN tốt -> chạy, POST
    w.submit_sn("GOOD")
    time.sleep(0.25)
    w.simulate_trigger()              # 1 đầu 8X
    time.sleep(0.35)
    results = [d for (t, d) in events if t == "result"]
    assert posted["n"] == 1 and posted["sn"] == "GOOD", "SN tốt phải POST 1 lần"
    assert results and results[-1]["ok"] is True
    print("2) SN tốt GOOD chạy đủ đầu -> POST thành công ✔")

    w.stop()
    print("\nTEST WORKER-CHECK-SN PASS ✔")


if __name__ == "__main__":
    main()
