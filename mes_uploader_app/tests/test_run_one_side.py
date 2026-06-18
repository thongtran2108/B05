# -*- coding: utf-8 -*-
"""Chế độ CHỈ CHẠY 1 BÊN: thanh ghi 'hoàn thành scan' (sn_result_reg) được ghi
cho CẢ 2 bên (cùng giá trị), để PLC không chờ bên còn lại.

- run_side='left'  -> ghi cả D4200 (trái) lẫn D4202 (phải) = 1.
- run_side='both'  -> chỉ ghi D4200 (trái), KHÔNG đụng D4202.

Chạy:  python -m tests.test_run_one_side
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader import mes_api
from mes_uploader.config import AppConfig, MaterialConfig, PathConfig
from mes_uploader.core.side_worker import SideWorker
from mes_uploader.hardware.plc_client import MockPlcClient

LEFT_REG = "D4200"
RIGHT_REG = "D4202"


def _run(run_side):
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "sample_data")
    cfg = AppConfig()
    cfg.simulation = True
    cfg.poll_interval_ms = 20
    cfg.paths = PathConfig(base_dir=base)
    cfg.paths.require_today = False
    cfg.paths.xlsx_only = False
    cfg.left.sn_result_reg = LEFT_REG
    cfg.right.sn_result_reg = RIGHT_REG
    cfg.run_side = run_side
    cfg.materials = [MaterialConfig("ABC", heads_8x=1)]
    cfg.api.api_8x.url = "http://mes/8x/upload"
    mes_api.post_payload = lambda url, payload, **kw: (True, 200, "OK")

    plc = MockPlcClient()
    writes = []
    orig = plc.write_word
    plc.write_word = lambda d, v: (writes.append((str(d).upper(), int(v))), orig(d, v))[1]

    w = SideWorker("left", cfg, plc, lambda et, **d: None)
    w.start()
    w.arm(cfg.materials[0], "8X")
    time.sleep(0.1)
    w.submit_sn("SN-1SIDE")
    time.sleep(0.2)
    w.simulate_trigger()
    time.sleep(0.3)
    w.stop()
    return writes


def main():
    print("== run_side='left' -> ghi cả 2 thanh ghi ==")
    wl = _run("left")
    assert (LEFT_REG, 1) in wl, wl
    assert (RIGHT_REG, 1) in wl, "bên kia (D4202) cũng phải được ghi: %r" % wl
    print("  D4200=1 và D4202=1 (ghi hộ bên phải)  ✔")

    print("\n== run_side='both' -> chỉ ghi bên trái ==")
    wb = _run("both")
    assert (LEFT_REG, 1) in wb, wb
    assert not any(d == RIGHT_REG for d, _ in wb), "both: KHÔNG được đụng D4202: %r" % wb
    print("  D4200=1, không ghi D4202  ✔")

    print("\nTEST RUN-ONE-SIDE PASS ✔")


if __name__ == "__main__":
    main()
