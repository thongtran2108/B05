# -*- coding: utf-8 -*-
"""Xác thực mở Setting: tài khoản + mật khẩu. Mặc định TDH / 8888.

Mật khẩu KHÔNG lưu dạng thô — chỉ lưu mã băm sha256 (cfg.auth_pass_hash). Để
trống = dùng mật khẩu mặc định '8888'. Đổi mật khẩu trong Setting sẽ ghi mã băm
mới. Tài khoản mặc định 'TDH' (cfg.auth_user).
"""

import hashlib

DEFAULT_USER = "TDH"
DEFAULT_PASS = "8888"
_SALT = "mes_uploader::"          # thêm muối cố định trước khi băm


def hash_pass(pwd):
    return hashlib.sha256((_SALT + str(pwd)).encode("utf-8")).hexdigest()


def current_user(cfg):
    return (getattr(cfg, "auth_user", "") or DEFAULT_USER).strip()


def _stored_hash(cfg):
    """Mã băm mật khẩu hiện hành (trống -> mật khẩu mặc định 8888)."""
    return (getattr(cfg, "auth_pass_hash", "") or "").strip() or hash_pass(DEFAULT_PASS)


def check(cfg, user, pwd):
    """Tài khoản + mật khẩu có đúng không?"""
    return (str(user).strip() == current_user(cfg)
            and hash_pass(pwd) == _stored_hash(cfg))


def verify_pass(cfg, pwd):
    """Chỉ kiểm mật khẩu (cho thao tác đổi mật khẩu — đã đăng nhập rồi)."""
    return hash_pass(pwd) == _stored_hash(cfg)


def set_password(cfg, new_pwd):
    """Đặt mật khẩu mới (ghi mã băm vào cfg.auth_pass_hash)."""
    cfg.auth_pass_hash = hash_pass(new_pwd)
