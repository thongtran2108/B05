# -*- coding: utf-8 -*-
"""Trigger/Done dùng THANH GHI WORD (D...) thay vì bit M (PLC Mitsubishi).

- pulse trên thanh ghi word -> worker nhận (giá trị != 0 = 'bật'), chạy 1 đầu.
- sau khi nhận: app reset trigger word về 0; done word kết thúc ở 0.

Chạy:  python -m tests.test_plc_word
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader import mes_api
from mes_uploader.config import AppConfig, MaterialConfig, PathConfig
from mes_uploader.hardware.mitsubishi_plc import is_word_device
from mes_uploader.hardware.plc_client import MockPlcClient
from mes_uploader.core.side_worker import SideWorker


def main():
    # is_word_device phân loại đúng bit (M) vs word (D/W/R)
    assert is_word_device("D100") and is_word_device("d10")
    assert is_word_device("W5") and is_word_device("R20")
    assert not is_word_device("M100") and not is_word_device("X0")
    assert not is_word_device("")            # rỗng -> coi như bit (an toàn)
    print("is_word_device phân loại đúng ✔")

    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "sample_data")
    cfg = AppConfig()
    cfg.simulation = True
    cfg.poll_interval_ms = 25
    cfg.paths = PathConfig(base_dir=base)
    cfg.paths.require_today = False
    cfg.materials = [MaterialConfig("ABC", heads_8x=1)]
    # Dùng THANH GHI WORD (D) cho trigger/done bên trái 8X
    cfg.left.trig_8x = "D10"
    cfg.left.done_8x = "D11"
    cfg.api.api_8x.url = "http://mes/8x/upload"

    captured = {}

    def fake_post(url, payload, **kw):
        captured["payload"] = payload
        return True, 200, "OK"

    mes_api.post_payload = fake_post

    events = []
    plc = MockPlcClient()
    w = SideWorker("left", cfg, plc, lambda et, **d: events.append((et, d)))
    w.start()
    w.arm(cfg.materials[0], "8X")
    time.sleep(0.1)
    w.submit_sn("SN-D-001")
    time.sleep(0.2)
    w.simulate_trigger()          # bật D10 = 1 (giá trị word)
    time.sleep(0.4)
    w.stop()

    readings = [d for (t, d) in events if t == "reading"]
    assert readings, "Phải chạy 1 đầu qua trigger WORD (D10)"
    assert captured.get("payload", {}).get("sn") == "SN-D-001", "phải POST đúng SN"
    # trigger word đã được app reset về 0; done word kết thúc ở 0
    assert plc.read_word("D10") == 0, "trigger word phải được reset về 0"
    assert plc.read_word("D11") == 0, "done word phải kết thúc ở 0"
    print("Trigger/Done qua thanh ghi WORD D10/D11 chạy đúng, reset về 0 ✔")
    print("\nTEST PLC-WORD PASS ✔")


if __name__ == "__main__":
    main()
