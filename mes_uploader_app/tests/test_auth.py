# -*- coding: utf-8 -*-
"""Xác thực mở Setting: mặc định TDH/8888; đổi mật khẩu; không lưu mật khẩu thô.

Chạy:  python -m tests.test_auth
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader.config import AppConfig
from mes_uploader.core import auth


def main():
    cfg = AppConfig()

    # 1) Mặc định: TDH / 8888
    print("== mặc định TDH/8888 ==")
    assert auth.current_user(cfg) == "TDH"
    assert auth.check(cfg, "TDH", "8888")
    assert not auth.check(cfg, "TDH", "1234")      # sai mật khẩu
    assert not auth.check(cfg, "abc", "8888")      # sai tài khoản
    print("  TDH/8888 đúng; sai pass/user bị chặn  ✔")

    # 2) Đổi mật khẩu
    print("\n== đổi mật khẩu ==")
    auth.set_password(cfg, "newpass")
    assert not auth.check(cfg, "TDH", "8888")      # mật khẩu cũ hết tác dụng
    assert auth.check(cfg, "TDH", "newpass")       # mật khẩu mới
    assert auth.verify_pass(cfg, "newpass")
    assert not auth.verify_pass(cfg, "8888")
    print("  đổi xong: 8888 hỏng, newpass đúng  ✔")

    # 3) KHÔNG lưu mật khẩu dạng thô (chỉ lưu mã băm)
    print("\n== không lưu mật khẩu thô ==")
    assert "newpass" not in (cfg.auth_pass_hash or "")
    assert len(cfg.auth_pass_hash) == 64          # sha256 hex
    print("  auth_pass_hash là sha256, không chứa mật khẩu thô  ✔")

    print("\nTEST AUTH PASS ✔")


if __name__ == "__main__":
    main()
