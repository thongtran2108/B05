# -*- coding: utf-8 -*-
"""Chặn 2 bên TRÙNG mã: bên kia đang chạy mã X thì bên này quét X bị CHẶN.

- ActiveSnRegistry: logic theo dõi SN đang chạy mỗi bên.
- Worker: registry báo 'bên kia đang giữ X' -> worker CHẶN (sn_rejected), không
  chạy; quét mã KHÁC thì nhận bình thường.

Chạy:  python -m tests.test_sn_dup_block
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader import mes_api
from mes_uploader.config import AppConfig, MaterialConfig, PathConfig
from mes_uploader.core.side_worker import SideWorker
from mes_uploader.core.sn_registry import ActiveSnRegistry
from mes_uploader.hardware.plc_client import MockPlcClient


def test_registry():
    print("== ActiveSnRegistry ==")
    r = ActiveSnRegistry()
    assert not r.taken_by_other("left", "X")
    r.acquire("right", "X")
    assert r.taken_by_other("left", "X")        # bên kia (right) đang giữ X
    assert not r.taken_by_other("right", "X")   # chính nó -> không tính
    assert not r.taken_by_other("left", "Y")    # mã khác -> không trùng
    r.release("right")
    assert not r.taken_by_other("left", "X")
    print("  acquire/taken_by_other/release  ✔")


def test_worker_blocks_dup():
    print("\n== worker chặn mã đang chạy ở bên kia ==")
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "sample_data")
    cfg = AppConfig()
    cfg.simulation = True
    cfg.poll_interval_ms = 20
    cfg.paths = PathConfig(base_dir=base)
    cfg.paths.require_today = False
    cfg.paths.xlsx_only = False
    cfg.materials = [MaterialConfig("ABC", heads_8x=1)]
    cfg.api.api_8x.url = "http://mes/8x/upload"
    mes_api.post_payload = lambda url, payload, **kw: (True, 200, "OK")

    reg = ActiveSnRegistry()
    reg.acquire("right", "DUP-1")               # giả lập bên PHẢI đang chạy DUP-1

    events = []
    w = SideWorker("left", cfg, MockPlcClient(),
                   lambda et, **d: events.append((et, d)), sn_registry=reg)
    w.start(); w.arm(cfg.materials[0], "8X"); time.sleep(0.1)

    # quét đúng mã bên phải đang chạy -> bị CHẶN
    w.submit_sn("DUP-1"); time.sleep(0.3)
    assert any(et == "sn_rejected" for et, _ in events), "phải chặn mã trùng"
    assert not any(et == "sn" for et, _ in events), "không được nhận (không 'sn')"
    print("  quét DUP-1 (bên phải đang chạy) -> bị chặn  ✔")

    # quét mã KHÁC -> nhận bình thường
    events.clear()
    w.submit_sn("OTHER-2"); time.sleep(0.3)
    assert any(et == "sn" for et, _ in events), "mã khác phải được nhận"
    print("  quét OTHER-2 (khác mã) -> nhận  ✔")
    w.stop()


def main():
    test_registry()
    test_worker_blocks_dup()
    print("\nTEST SN-DUP-BLOCK PASS ✔")


if __name__ == "__main__":
    main()
