# -*- coding: utf-8 -*-
"""Kiểm thử: SN nhiều đầu -> ảnh mỗi đầu có hậu tố _#<thứ tự> (không cần mạng/Qt).

Mô phỏng bên trái mã liệu ABC (2 đầu 8X) -> quét SN -> 2 lần tín hiệu PLC.
Kỳ vọng worker tải ảnh cho từng đầu với index 1 rồi 2, và tên file đích là
<SN>_<YYYY.MM.DD HH.MM.SS>_#1 / _#2.

Chạy:  python -m tests.test_image_index
"""

import datetime
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader import image_uploader, mes_api
from mes_uploader.config import AppConfig, MaterialConfig, PathConfig
from mes_uploader.core.side_worker import SideWorker
from mes_uploader.hardware.plc_client import MockPlcClient


def _mk(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def main():
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "sample_data")
    cfg = AppConfig()
    cfg.simulation = True
    cfg.poll_interval_ms = 20
    cfg.paths = PathConfig(base_dir=base)
    cfg.paths.require_today = False          # data mẫu + ảnh: lấy ngày mới nhất
    cfg.materials = [MaterialConfig("ABC", heads_8x=2)]
    cfg.api.api_8x.url = "http://mes/8x/upload"

    # bật ảnh cho đầu 8X: nguồn + đích là thư mục tạm
    root = tempfile.mkdtemp(prefix="img_idx_")
    src = os.path.join(root, "src8x")
    up = os.path.join(root, "up8x")
    cfg.images.enabled = True
    cfg.images.img_8x.source_dir = src
    cfg.images.img_8x.upload_dir = up
    day = datetime.datetime.now().strftime("%Y%m%d")
    _mk(os.path.join(src, "Image", day, "CCD1", "OK", "ok.jpg"), b"OKIMG")
    _mk(os.path.join(src, "Image", day, "CCD1", "NG", "ng.jpg"), b"NGIMG")

    mes_api.post_payload = lambda url, payload, **kw: (True, 200, "OK")

    # bắt index truyền vào upload, vẫn cho copy thật để kiểm tra tên file
    calls = []
    orig_upload = image_uploader.upload_latest_image

    def spy(*a, **kw):
        calls.append(kw.get("index"))
        return orig_upload(*a, **kw)

    image_uploader.upload_latest_image = spy
    try:
        w = SideWorker("left", cfg, MockPlcClient(), lambda et, **d: None)
        w.start()
        w.arm(cfg.materials[0], "8X")        # 2 đầu 8X
        time.sleep(0.1)
        w.submit_sn("SN-IMG-7")
        time.sleep(0.2)
        for _ in range(2):                   # 2 lần tín hiệu PLC -> 2 đầu
            w.simulate_trigger()
            time.sleep(0.3)
        time.sleep(0.4)
        w.stop()
    finally:
        image_uploader.upload_latest_image = orig_upload

    print("index mỗi đầu:", calls)
    names = sorted(fn for _d, _s, fns in os.walk(up) for fn in fns)
    print("file đích:", names)

    assert calls == [1, 2], "Worker phải tải ảnh đầu #1 rồi #2, nhận: %r" % calls
    assert any(n.endswith("_#1.jpg") for n in names), "Thiếu ảnh _#1"
    assert any(n.endswith("_#2.jpg") for n in names), "Thiếu ảnh _#2"
    # tên đủ định dạng <SN>_<YYYY.MM.DD HH.MM.SS>_#<idx>.<ext>
    assert all(n.startswith("SN-IMG-7_") for n in names)
    print("\nTEST IMAGE-INDEX PASS ✔")


if __name__ == "__main__":
    main()
