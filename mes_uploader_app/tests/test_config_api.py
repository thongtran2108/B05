# -*- coding: utf-8 -*-
"""Kiểm thử API riêng theo loại đầu (không cần Qt / phần cứng).

- head_api() chọn đúng HeadApiConfig theo 4X / 8X / 16X.
- Nạp cấu hình CŨ (1 API phẳng) -> tự nhân ra cho cả 3 đầu (độc lập).
- Nạp cấu hình MỚI (api_4x/api_8x/api_16x) -> mỗi đầu 1 endpoint riêng.
- save/load roundtrip giữ nguyên 3 API.

Chạy:  python -m tests.test_config_api
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader.config import (AppConfig, ApiConfig, HeadApiConfig, head_api,
                                 load_config, save_config, _api_from_dict)


def main():
    # 1) head_api chọn đúng đối tượng theo loại đầu
    print("== head_api chọn đúng API theo loại đầu ==")
    api = ApiConfig()
    assert head_api(api, "4X") is api.api_4x
    assert head_api(api, "8X") is api.api_8x
    assert head_api(api, "16X") is api.api_16x
    print("  OK")

    # 2) Migrate cấu hình CŨ (1 API phẳng) -> nhân ra cho cả 3 đầu, độc lập
    print("\n== Migrate cấu hình cũ (1 API chung -> 3 đầu) ==")
    old = {
        "url": "http://old/upload",
        "post_ok_contains": "OKK",
        "check_enabled": True,
        "check_url_prefix": "http://old/check?sn=",
        "check_ok_contains": "Z",
        "timeout": 9.0,
        "retries": 7,
    }
    a = _api_from_dict(old)
    assert a.timeout == 9.0 and a.retries == 7         # tham số chung giữ nguyên
    for h in (a.api_4x, a.api_8x, a.api_16x):
        assert h.url == "http://old/upload"
        assert h.post_ok_contains == "OKK"
        assert h.check_url_prefix == "http://old/check?sn="
        assert h.check_ok_value == "Z"   # khóa cũ 'check_ok_contains' -> 'check_ok_value'
    a.api_4x.url = "ĐỔI"                                # phải độc lập, không share
    assert a.api_8x.url == "http://old/upload"
    print("  OK (3 đầu nhận cùng API cũ, sửa 1 đầu không ảnh hưởng đầu khác)")

    # 3) Cấu trúc MỚI: mỗi đầu URL riêng
    print("\n== Cấu hình mới: mỗi đầu 1 endpoint riêng ==")
    new = {
        "timeout": 5.0,
        "api_4x": {"url": "http://u/4x"},
        "api_8x": {"url": "http://u/8x", "check_ok_contains": "Q"},  # khóa cũ trong sub-dict
        "api_16x": {"url": "http://u/16x", "check_url_prefix": "http://u/16x/check?sn=",
                    "check_ok_value": "9"},
    }
    a2 = _api_from_dict(new)
    assert (a2.api_4x.url, a2.api_8x.url, a2.api_16x.url) == (
        "http://u/4x", "http://u/8x", "http://u/16x")
    assert a2.api_16x.check_url_prefix == "http://u/16x/check?sn="
    # khóa cũ 'check_ok_contains' trong sub-dict -> chuyển sang 'check_ok_value'
    assert a2.api_8x.check_ok_value == "Q"
    assert a2.api_16x.check_ok_value == "9"
    # field không khai báo -> dùng mặc định HeadApiConfig
    assert a2.api_4x.post_ok_contains == HeadApiConfig().post_ok_contains
    assert a2.api_4x.check_ok_value == HeadApiConfig().check_ok_value   # "0"
    print("  OK")

    # 4) save/load roundtrip giữ nguyên 3 API
    print("\n== save/load roundtrip ==")
    cfg = AppConfig()
    cfg.api.api_4x.url = "http://r/4x"
    cfg.api.api_8x.post_ok_contains = "DONE"
    cfg.api.api_16x.check_url_prefix = "http://r/16x/check?sn="
    fd, path = tempfile.mkstemp(suffix=".json"); os.close(fd)
    save_config(cfg, path)
    loaded = load_config(path); os.remove(path)
    assert loaded.api.api_4x.url == "http://r/4x"
    assert loaded.api.api_8x.post_ok_contains == "DONE"
    assert head_api(loaded.api, "16X").check_url_prefix == "http://r/16x/check?sn="
    print("  OK")

    print("\nTEST CONFIG-API PASS ✔")


if __name__ == "__main__":
    main()
