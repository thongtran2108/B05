# -*- coding: utf-8 -*-
"""Kiểm thử: SN nhiều đầu -> ghi LẠI thanh ghi kết quả SN = 1 cho mỗi đầu kế.

PLC reset thanh ghi kết quả SN (vd D4200) về 0 sau mỗi đầu, nên với SN nhiều
đầu app phải ghi lại 1 trước mỗi đầu tiếp theo; đầu cuối xong thì thôi.

  - 2 đầu 8X  -> D4200 được ghi = 1 đúng 2 lần (kiểm SN + ghi lại trước đầu 2).
  - 1 đầu 8X  -> D4200 chỉ ghi = 1 một lần (không ghi lại).

Chạy:  python -m tests.test_plc_sn_rearm
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader import mes_api
from mes_uploader.config import AppConfig, MaterialConfig, PathConfig
from mes_uploader.hardware.plc_client import MockPlcClient
from mes_uploader.core.side_worker import SideWorker

REG = "D4200"          # thanh ghi kết quả SN bên trái (theo cấu hình)


def _run(heads_8x):
    """Chạy 1 SN với 'heads_8x' đầu; trả về số lần D4200 được ghi = 1."""
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "sample_data")
    cfg = AppConfig()
    cfg.simulation = True
    cfg.poll_interval_ms = 20
    cfg.paths = PathConfig(base_dir=base)
    cfg.paths.require_today = False
    cfg.left.sn_result_reg = REG            # ghi 1=OK / 2=NG về D4200
    cfg.materials = [MaterialConfig("ABC", heads_8x=heads_8x)]
    cfg.api.api_8x.url = "http://mes/8x/upload"
    mes_api.post_payload = lambda url, payload, **kw: (True, 200, "OK")

    plc = MockPlcClient()
    writes = []                              # ghi nhận mọi write_word
    orig_ww = plc.write_word

    def spy_ww(dev, val):
        writes.append((str(dev).upper(), int(val)))
        return orig_ww(dev, val)

    plc.write_word = spy_ww

    w = SideWorker("left", cfg, plc, lambda et, **d: None)
    w.start()
    w.arm(cfg.materials[0], "8X")
    time.sleep(0.1)
    w.submit_sn("SN-REARM")
    time.sleep(0.2)
    for _ in range(heads_8x):                # mỗi đầu 1 tín hiệu PLC
        w.simulate_trigger()
        time.sleep(0.3)
    time.sleep(0.3)
    w.stop()

    ones = [(d, v) for (d, v) in writes if d == REG and v == 1]
    return len(ones), writes


def main():
    # 2 đầu: ghi D4200 = 1 hai lần (kiểm SN + ghi lại trước đầu 2)
    print("== SN 2 đầu 8X ==")
    n2, writes2 = _run(2)
    print("  số lần ghi %s = 1:" % REG, n2)
    print("  toàn bộ write_word:", writes2)
    assert n2 == 2, "SN 2 đầu phải ghi %s=1 đúng 2 lần, thực tế %d" % (REG, n2)

    # 1 đầu: chỉ ghi D4200 = 1 một lần (không ghi lại)
    print("\n== SN 1 đầu 8X ==")
    n1, writes1 = _run(1)
    print("  số lần ghi %s = 1:" % REG, n1)
    print("  toàn bộ write_word:", writes1)
    assert n1 == 1, "SN 1 đầu chỉ ghi %s=1 một lần, thực tế %d" % (REG, n1)

    print("\nTEST PLC-SN-REARM PASS ✔")


if __name__ == "__main__":
    main()
