# -*- coding: utf-8 -*-
"""Kiểm thử: công tắc tải 'timer' + ghi nhật ký ra file (audit).

- build_payload: include_timer True -> có 'timer'; False -> KHÔNG có 'timer'.
- Worker: cfg.api.upload_timer điều khiển payload thật.
- audit: khi bật, ghi file scan_YYYYMMDD.log gồm trạng thái quét mã, DỮ LIỆU
  gửi MES và PHẢN HỒI của MES.

Chạy:  python -m tests.test_log_and_timer
"""

import glob
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile

from mes_uploader import audit, mes_api
from mes_uploader.config import AppConfig, MaterialConfig, PathConfig
from mes_uploader.core.side_worker import SideWorker
from mes_uploader.hardware.plc_client import MockPlcClient


def _run_worker(upload_timer, log_dir):
    """Chạy 1 SN (2 đầu 8X) với cờ upload_timer; trả về payload đã POST."""
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "sample_data")
    cfg = AppConfig()
    cfg.simulation = True
    cfg.poll_interval_ms = 20
    cfg.paths = PathConfig(base_dir=base)
    cfg.paths.require_today = False
    cfg.materials = [MaterialConfig("ABC", heads_8x=2)]
    cfg.api.api_8x.url = "http://mes/8x/upload"
    cfg.api.api_8x.station_name = "ST-8X"
    cfg.api.upload_timer = upload_timer

    audit.configure(log_dir, True)
    cap = {}
    mes_api.post_payload = lambda u, p, **k: (cap.update(payload=p)
                                              or (True, 200, "RESP-OK-42"))
    w = SideWorker("left", cfg, MockPlcClient(), lambda et, **d: None)
    w.start()
    w.arm(cfg.materials[0], "8X")
    time.sleep(0.1)
    w.submit_sn("SN-LT-1")
    time.sleep(0.2)
    for _ in range(2):
        w.simulate_trigger()
        time.sleep(0.3)
    time.sleep(0.4)
    w.stop()
    return cap.get("payload", {})


def main():
    # 1) build_payload: bật/tắt 'timer'
    print("== build_payload include_timer ==")
    readings = [{"values": [1.0, 2.0]}, {"values": [3.0]}]
    on = mes_api.build_payload("S", readings, "ST", "E", include_timer=True)
    off = mes_api.build_payload("S", readings, "ST", "E", include_timer=False)
    assert "timer" in on and on["timer"], on
    assert "timer" not in off, off
    assert set(off) == {"sn", "stationName", "empNo"}

    # 2) Worker TẮT timer -> payload không có 'timer'; log ghi "(không gửi)"
    print("\n== worker: TẮT timer + ghi log ==")
    d_off = tempfile.mkdtemp(prefix="log_off_")
    p_off = _run_worker(False, d_off)
    print("  payload:", p_off)
    assert "timer" not in p_off, p_off
    log_off = open(glob.glob(os.path.join(d_off, "scan_*.log"))[0],
                   encoding="utf-8").read()
    assert "SN-LT-1" in log_off                      # trạng thái quét mã
    assert "DỮ LIỆU gửi MES" in log_off              # dữ liệu đã gửi
    assert "(không gửi)" in log_off                  # timer tắt
    assert "PHẢN HỒI MES" in log_off and "RESP-OK-42" in log_off   # phản hồi MES

    # 3) Worker BẬT timer -> payload có 'timer'; log ghi giá trị timer
    print("\n== worker: BẬT timer + ghi log ==")
    d_on = tempfile.mkdtemp(prefix="log_on_")
    p_on = _run_worker(True, d_on)
    print("  payload.timer:", p_on.get("timer"))
    assert p_on.get("timer"), p_on
    log_on = open(glob.glob(os.path.join(d_on, "scan_*.log"))[0],
                  encoding="utf-8").read()
    assert "timer=L1:" in log_on, log_on             # dữ liệu timer xuất hiện trong log

    # 4) audit tắt -> không tạo file
    print("\n== audit tắt -> không ghi file ==")
    d_none = tempfile.mkdtemp(prefix="log_none_")
    audit.configure(d_none, False)
    audit.log("CCD1", "dòng này không được ghi")
    assert glob.glob(os.path.join(d_none, "scan_*.log")) == []

    print("\nTEST LOG-AND-TIMER PASS ✔")


if __name__ == "__main__":
    main()
