# -*- coding: utf-8 -*-
"""Kiểm thử 'Chờ dòng mới (tối đa)' (trigger_delay_ms) — semantics MỚI:

Sau khi nhận trigger PLC, worker CHỜ TỐI ĐA khoảng này cho tới khi file có DÒNG
MỚI rồi mới đọc. Với file TĨNH (không có dòng mới):
  - delay = 0   -> đọc ngay 'dòng hiện có' (fallback) -> có sự kiện 'reading'.
  - delay > 0   -> chờ rồi QUÁ THỜI GIAN -> HỦY (KHÔNG dùng dòng cũ) -> 'error'.
(Trường hợp dòng mới tới giữa chừng: xem test_wait_new_row.)

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


def _run_events(delay_ms):
    """Chạy 1 đầu trên file mẫu TĨNH; trả về tập loại sự kiện worker phát ra."""
    cfg = AppConfig()
    cfg.simulation = True
    cfg.poll_interval_ms = 20
    cfg.trigger_delay_ms = delay_ms
    cfg.paths = PathConfig(base_dir=SAMPLE)
    cfg.paths.require_today = False
    cfg.paths.xlsx_only = False
    cfg.materials = [MaterialConfig("ABC", heads_8x=1)]
    mes_api.post_payload = lambda *a, **k: (True, 200, "OK")

    seen = set()
    w = SideWorker("left", cfg, MockPlcClient(), lambda et, **d: seen.add(et))
    w.start()
    w.arm(cfg.materials[0], "8X")
    time.sleep(0.1)
    w.submit_sn("SN-DELAY")
    time.sleep(0.2)
    w.simulate_trigger()
    time.sleep(0.9)                     # đủ để qua mốc chờ 400ms
    w.stop()
    return seen


def test_delay_max_wait():
    print("== delay là 'chờ tối đa cho dòng mới' (file tĩnh) ==")
    ev0 = _run_events(0)
    assert "reading" in ev0, "delay=0 -> đọc ngay dòng hiện có (có 'reading')"
    ev1 = _run_events(400)
    assert "error" in ev1, "delay=400 + không dòng mới -> HỦY ('error')"
    assert "reading" not in ev1, "delay>0 quá giờ -> KHÔNG dùng dòng cũ"
    print("  delay=0 -> reading | delay=400 (file tĩnh) -> error (hủy)  ✔")


def test_config_roundtrip():
    print("\n== cấu hình trigger_delay_ms lưu/nạp JSON ==")
    cfg = AppConfig()
    cfg.trigger_delay_ms = 750
    path = os.path.join(tempfile.mkdtemp(), "cfg.json")
    save_config(cfg, path)
    again = load_config(path)
    assert again.trigger_delay_ms == 750, again.trigger_delay_ms
    assert AppConfig().trigger_delay_ms == 0      # cấu hình cũ (không có khóa) -> 0
    print("  OK (lưu 750, nạp lại 750; mặc định 0)")


def main():
    test_delay_max_wait()
    test_config_roundtrip()
    print("\nTEST TRIGGER-DELAY PASS ✔")


if __name__ == "__main__":
    main()
