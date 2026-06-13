# -*- coding: utf-8 -*-
"""Kiểm thử 'Chờ sau tín hiệu' (trigger_delay_ms): sau khi nhận trigger PLC,
worker chờ thêm khoảng cấu hình rồi MỚI đọc số liệu + lấy ảnh.

- So sánh thời điểm xảy ra sự kiện 'reading' giữa delay=0 và delay=400 ms
  (khử thời gian xử lý nền) -> phải chênh ≳ độ trễ đã đặt.
- Cấu hình round-trip qua JSON.

Chạy:  python -m tests.test_trigger_delay
"""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader import mes_api
from mes_uploader.config import (AppConfig, MaterialConfig, PathConfig,
                                 load_config, save_config)
from mes_uploader.core.side_worker import SideWorker
from mes_uploader.hardware.plc_client import MockPlcClient

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "sample_data")


def _time_to_reading(delay_ms):
    """Đo khoảng từ lúc bật trigger tới khi worker phát sự kiện 'reading'."""
    cfg = AppConfig()
    cfg.simulation = True
    cfg.poll_interval_ms = 20
    cfg.trigger_delay_ms = delay_ms
    cfg.paths = PathConfig(base_dir=SAMPLE)
    cfg.paths.require_today = False
    cfg.materials = [MaterialConfig("ABC", heads_8x=1)]
    mes_api.post_payload = lambda *a, **k: (True, 200, "OK")

    captured = {}

    def on_event(et, **d):
        if et == "reading" and "t" not in captured:
            captured["t"] = time.time()

    w = SideWorker("left", cfg, MockPlcClient(), on_event)
    w.start()
    w.arm(cfg.materials[0], "8X")
    time.sleep(0.1)
    w.submit_sn("SN-DELAY")
    time.sleep(0.2)
    t0 = time.time()
    w.simulate_trigger()
    deadline = time.time() + 5
    while "t" not in captured and time.time() < deadline:
        time.sleep(0.01)
    w.stop()
    assert "t" in captured, "phải có sự kiện 'reading'"
    return captured["t"] - t0


def test_delay_waits_before_reading():
    print("== delay=0 vs delay=400ms ==")
    fast = _time_to_reading(0)
    slow = _time_to_reading(400)
    print("  delay=0   -> %.3fs tới khi đọc" % fast)
    print("  delay=400 -> %.3fs tới khi đọc" % slow)
    # chênh lệch phải xấp xỉ độ trễ (để biên 0.30s cho máy chậm)
    assert slow - fast >= 0.30, "chờ chưa đủ: slow=%.3f fast=%.3f" % (slow, fast)
    print("  OK: chênh %.3fs ≳ 0.30s" % (slow - fast))


def test_config_roundtrip():
    print("\n== cấu hình trigger_delay_ms lưu/nạp JSON ==")
    cfg = AppConfig()
    cfg.trigger_delay_ms = 750
    path = os.path.join(tempfile.mkdtemp(), "cfg.json")
    save_config(cfg, path)
    again = load_config(path)
    assert again.trigger_delay_ms == 750, again.trigger_delay_ms
    # cấu hình CŨ (không có khóa) -> mặc định 0
    assert AppConfig().trigger_delay_ms == 0
    print("  OK (lưu 750, nạp lại 750; mặc định 0)")


def main():
    test_delay_waits_before_reading()
    test_config_roundtrip()
    print("\nTEST TRIGGER-DELAY PASS ✔")


if __name__ == "__main__":
    main()
