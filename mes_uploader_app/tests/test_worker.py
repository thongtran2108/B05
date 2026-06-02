# -*- coding: utf-8 -*-
"""Kiểm thử headless máy trạng thái SideWorker (không cần Qt / phần cứng).

Mô phỏng: bật bên trái với mã liệu ABC (2 đầu 8X) -> quét SN -> giả lập
2 lần tín hiệu PLC -> kỳ vọng gộp 2 đầu và POST 1 lần lên MES.

Chạy:  python -m tests.test_worker
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
    cfg.paths.require_today = False    # data mẫu cố định ngày cũ
    cfg.materials = [MaterialConfig("ABC", project="Chuyên án A",
                                    heads_8x=2, heads_16x=1)]
    # API riêng theo đầu: chọn 8X -> POST phải đi tới URL của đầu 8X
    cfg.api.api_8x.url = "http://mes/8x/upload"

    # chặn POST thật, ghi lại payload
    captured = {}

    def fake_post(url, payload, **kw):
        captured["url"] = url
        captured["payload"] = payload
        return True, 200, "OK"

    mes_api.post_payload = fake_post   # monkeypatch

    events = []
    lock_print = []

    def on_event(etype, **data):
        events.append((etype, data))
        if etype in ("log", "status"):
            lock_print.append("[%s] %s" % (etype, data.get("text", data)))

    plc = MockPlcClient()
    w = SideWorker("left", cfg, plc, on_event)
    w.start()

    abc = cfg.materials[0]
    w.arm(abc, "8X")          # 2 đầu 8X
    time.sleep(0.1)
    w.submit_sn("SN-LEFT-001")
    time.sleep(0.2)

    # giả lập 2 lần tín hiệu PLC
    for i in range(2):
        w.simulate_trigger()
        time.sleep(0.3)

    time.sleep(0.3)
    w.stop()

    print("\n".join(lock_print))
    print("\n--- KẾT QUẢ ---")
    results = [d for (t, d) in events if t == "result"]
    assert captured.get("payload"), "Phải có payload POST lên MES"
    payload = captured["payload"]
    print("POST url:", captured["url"])
    print("payload.sn:", payload["sn"])
    print("payload.result:", payload["result"])
    print("payload.data: %d đầu, đầu1 có %d giá trị"
          % (len(payload["data"]), len(payload["data"][0])))
    assert payload["sn"] == "SN-LEFT-001"
    assert len(payload["data"]) == 2, "Phải gộp đúng 2 đầu"
    assert captured["url"] == "http://mes/8x/upload", "POST phải đi tới API đầu 8X"
    # body có thêm chuyên án / mã liệu / loại đầu đo đang chạy
    assert payload["project"] == "Chuyên án A", "body phải có chuyên án đang chạy"
    assert payload["material"] == "ABC", "body phải có mã liệu đang chạy"
    assert payload["measuring_head"] == "8X", "body phải có loại đầu đo đang chạy"
    assert results and results[-1]["sn"] == "SN-LEFT-001"
    print("\nTEST WORKER PASS ✔")


if __name__ == "__main__":
    main()
