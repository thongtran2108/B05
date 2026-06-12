# -*- coding: utf-8 -*-
"""Kết nối PLC DÙNG CHUNG: 1 client cho cả app, side không tự đóng (owns_plc).

Chạy:  python -m tests.test_shared_plc
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader.config import AppConfig, MaterialConfig, PathConfig
from mes_uploader.hardware.plc_client import (make_shared_plc, MockPlcClient,
                                             PlcClient)
from mes_uploader.core.side_worker import SideWorker


def main():
    # 1) make_shared_plc theo chế độ/giao thức
    sim = AppConfig()                       # simulation=True
    assert isinstance(make_shared_plc(sim), MockPlcClient)
    real = AppConfig(); real.simulation = False
    assert isinstance(make_shared_plc(real), PlcClient)
    real.plc.protocol = "modbus"
    from mes_uploader.hardware.modbus_tcp import ModbusTcpClient
    assert isinstance(make_shared_plc(real), ModbusTcpClient)
    print("1) make_shared_plc đúng loại theo chế độ/giao thức ✔")

    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "sample_data")
    cfg = AppConfig()
    cfg.simulation = True
    cfg.poll_interval_ms = 30
    cfg.paths = PathConfig(base_dir=base); cfg.paths.require_today = False
    cfg.materials = [MaterialConfig("ABC", heads_8x=1)]

    # 2) 2 worker DÙNG CHUNG 1 client; stop KHÔNG đóng (owns_plc=False)
    plc = make_shared_plc(cfg); plc.connect()
    cb = lambda *a, **k: None
    wl = SideWorker("left", cfg, plc, cb, owns_plc=False)
    wr = SideWorker("right", cfg, plc, cb, owns_plc=False)
    wl.start(); wr.start(); time.sleep(0.05)
    wl.stop(); wr.stop()
    assert plc.is_connected, "kết nối CHUNG không được đóng khi 1 bên dừng"
    print("2) 2 bên dùng chung 1 client, dừng không đóng kết nối chung ✔")

    # 3) owns_plc=True (mặc định) -> tự đóng khi dừng
    own = MockPlcClient(); own.connect()
    w = SideWorker("left", cfg, own, cb)        # owns_plc mặc định True
    w.start(); time.sleep(0.05); w.stop()
    assert not own.is_connected, "owns_plc=True phải tự đóng khi dừng"
    print("3) owns_plc=True -> tự đóng khi dừng ✔")

    print("\nTEST SHARED-PLC PASS ✔")


if __name__ == "__main__":
    main()
