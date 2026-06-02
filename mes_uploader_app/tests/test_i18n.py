# -*- coding: utf-8 -*-
"""Kiểm thử đa ngôn ngữ (i18n) — không cần Qt / phần cứng.

- tr() trả về chuỗi nguồn khi ở tiếng Việt, trả về bản dịch cho zh / en.
- Đổi ngôn ngữ gọi lại listener (cơ chế retranslate của giao diện).
- Mọi bản dịch giữ nguyên ký tự định dạng %s / %d của chuỗi nguồn.
- Cấu hình lưu/nạp giữ trường 'language'; cấu hình cũ (thiếu) -> mặc định 'vi'.
- Worker phát log/status theo đúng ngôn ngữ đang chọn.

Chạy:  python -m tests.test_i18n
"""

import os
import re
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader import i18n
from mes_uploader.config import (AppConfig, MaterialConfig, _from_dict,
                                 load_config, save_config)
from mes_uploader.hardware.plc_client import MockPlcClient
from mes_uploader.core.side_worker import SideWorker

_SPEC = re.compile(r"%[#0\- +]*\d*(?:\.\d+)?[sdifgxXeEoc%]")


def main():
    try:
        # 1) tr(): tiếng Việt = chuỗi nguồn; zh/en = bản dịch
        print("== tr() theo ngôn ngữ ==")
        i18n.set_language("vi")
        assert i18n.tr("Setting") == "Setting"
        i18n.set_language("zh")
        assert i18n.tr("Setting") == "设置"
        assert i18n.tr("Bắt đầu") == "开始"
        i18n.set_language("en")
        assert i18n.tr("Setting") == "Settings"
        assert i18n.tr("Dừng") == "Stop"
        # khóa không có trong bảng -> trả về nguyên văn (không vỡ)
        assert i18n.tr("__chuỗi_không_tồn_tại__") == "__chuỗi_không_tồn_tại__"
        print("  OK")

        # 2) Đổi ngôn ngữ gọi lại listener
        print("\n== listener khi đổi ngôn ngữ ==")
        hits = {"n": 0}
        cb = lambda: hits.__setitem__("n", hits["n"] + 1)
        i18n.add_listener(cb)
        i18n.set_language("vi")
        i18n.set_language("zh")
        assert hits["n"] >= 2
        i18n.remove_listener(cb)
        before = hits["n"]
        i18n.set_language("en")
        assert hits["n"] == before, "listener đã gỡ không được gọi nữa"
        print("  OK (gọi %d lần, gỡ rồi không gọi nữa)" % before)

        # 3) Mã ngôn ngữ lạ -> về mặc định 'vi'
        print("\n== normalize ngôn ngữ lạ ==")
        i18n.set_language("xx")
        assert i18n.current_language() == "vi"
        print("  OK")

        # 4) Mọi bản dịch giữ nguyên ký tự định dạng %s/%d
        print("\n== ký tự định dạng nhất quán ==")
        bad = 0
        for src, entry in i18n._TR.items():
            s = _SPEC.findall(src)
            for lang, txt in entry.items():
                if _SPEC.findall(txt) != s:
                    bad += 1
                    print("  MISMATCH [%s] %r -> %r" % (lang, src, txt))
        assert bad == 0
        print("  OK (%d mục, 0 lệch)" % len(i18n._TR))

        # 5) Cấu hình lưu/nạp giữ 'language'; cấu hình cũ thiếu -> 'vi'
        print("\n== cấu hình giữ language + tương thích cũ ==")
        cfg = AppConfig(); cfg.language = "zh"
        fd, path = tempfile.mkstemp(suffix=".json"); os.close(fd)
        save_config(cfg, path)
        loaded = load_config(path); os.remove(path)
        assert loaded.language == "zh"
        legacy = _from_dict(AppConfig, {"simulation": False})   # JSON cũ, không có language
        assert legacy.language == "vi"
        print("  OK (roundtrip giữ 'zh', cấu hình cũ mặc định 'vi')")

        # 6) Worker phát status theo đúng ngôn ngữ đang chọn
        print("\n== worker phát log theo ngôn ngữ ==")
        wcfg = AppConfig(); wcfg.simulation = True; wcfg.poll_interval_ms = 20
        wcfg.materials = [MaterialConfig("ABC", heads_8x=1)]
        expect = {"zh": "已启动", "en": "Started", "vi": "Đã bật"}
        for lang, needle in expect.items():
            i18n.set_language(lang)
            cap = []
            w = SideWorker("left", wcfg, MockPlcClient(),
                           lambda et, **d: cap.append(d.get("text", ""))
                           if et == "status" else None)
            w.start(); w.arm(wcfg.materials[0], "8X"); time.sleep(0.05); w.stop()
            joined = " | ".join(cap)
            assert needle in joined, "[%s] thiếu %r trong %r" % (lang, needle, joined)
        print("  OK (zh/en/vi)")

        print("\nTEST I18N PASS ✔")
    finally:
        i18n.set_language("vi")   # trả lại mặc định, tránh ảnh hưởng tiến trình khác


if __name__ == "__main__":
    main()
