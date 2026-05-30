# -*- coding: utf-8 -*-
"""Worker khi THIẾU dữ liệu của ngày hôm nay: phải báo lỗi và KHÔNG POST.

Chạy:  python -m tests.test_worker_missing_today
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader import mes_api
from mes_uploader.config import AppConfig, MaterialConfig, PathConfig
from mes_uploader.hardware.plc_client import MockPlcClient
from mes_uploader.core.side_worker import SideWorker


def main():
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "sample_data")
    cfg = AppConfig()
    cfg.simulation = True
    cfg.poll_interval_ms = 30
    cfg.paths = PathConfig(base_dir=base)
    cfg.paths.require_today = True     # bắt buộc ngày hôm nay -> data mẫu (ngày cũ) sẽ thiếu
    cfg.materials = [MaterialConfig("ABC", heads_8x=2, heads_16x=1)]

    posted = {"called": False}

    def fake_post(url, payload, **kw):
        posted["called"] = True
        return True, 200, "OK"

    mes_api.post_payload = fake_post

    events = []
    w = SideWorker("left", cfg, MockPlcClient(),
                   lambda et, **d: events.append((et, d)))
    w.start()
    w.arm(cfg.materials[0], "8X")
    time.sleep(0.1)
    w.submit_sn("SN-NO-DATA")
    time.sleep(0.2)
    w.simulate_trigger()          # tín hiệu chạy -> reader báo thiếu dữ liệu hôm nay
    time.sleep(0.4)
    w.stop()

    errors = [d for (t, d) in events if t == "error"]
    results = [d for (t, d) in events if t == "result"]

    for (t, d) in events:
        if t in ("log", "status", "error"):
            print("[%s] %s" % (t, d.get("text") or d.get("message") or d))

    assert errors, "Phải phát sự kiện 'error' khi thiếu dữ liệu hôm nay"
    assert "20" in errors[-1]["message"], "Thông báo lỗi nên kèm ngày"
    assert not posted["called"], "KHÔNG được POST khi thiếu dữ liệu"
    assert not results, "Không có result thành công cho SN bị hủy"
    print("\nTEST WORKER-MISSING-TODAY PASS ✔")


if __name__ == "__main__":
    main()
