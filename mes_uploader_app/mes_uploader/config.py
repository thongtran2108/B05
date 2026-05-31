# -*- coding: utf-8 -*-
"""Cấu hình phần mềm: nạp / lưu từ file JSON.

Toàn bộ thiết lập (PLC, API, đường dẫn file dữ liệu, cổng COM của 2 tay
scan, địa chỉ bit handshake, danh sách mã liệu...) được gom vào AppConfig
và lưu ra 1 file JSON để chỉnh trong phần Setting trên giao diện.
"""

import json
import os
from dataclasses import dataclass, field, asdict, fields, is_dataclass
from typing import List


# ---------------------------------------------------------------------- #
#  Mã liệu: mỗi mã có số đầu 8X và số đầu 16X khác nhau                   #
# ---------------------------------------------------------------------- #
@dataclass
class MaterialConfig:
    name: str = ""          # tên mã liệu, vd "ABC"
    heads_8x: int = 0       # số đầu 8X  -> số lần chạy khi chọn 8X
    heads_16x: int = 0      # số đầu 16X -> số lần chạy khi chọn 16X


# ---------------------------------------------------------------------- #
#  Cấu hình 1 bên (Trái / Phải)                                          #
# ---------------------------------------------------------------------- #
@dataclass
class SideConfig:
    name: str = "LEFT"            # "LEFT" hoặc "RIGHT"
    scanner_port: str = "COM1"    # cổng COM của tay scan bên này
    scanner_baud: int = 9600
    ccd_prefix: str = "CCD1"      # CCD1 = bên trái, CCD2 = bên phải

    # --- Địa chỉ bit handshake với PLC (Mitsubishi) ---
    # trig_*: bit PLC bật =1 báo "chạy" (app đọc - poll)
    # done_*: bit app ghi =1 báo "đã lấy xong dữ liệu" về PLC
    trig_8x: str = "M100"
    done_8x: str = "M101"
    trig_16x: str = "M110"
    done_16x: str = "M111"

    # PLC riêng cho bên này (để trống = dùng PLC chung trong PlcConfig)
    plc_ip: str = ""
    plc_port: int = 0


# ---------------------------------------------------------------------- #
#  PLC chung                                                              #
# ---------------------------------------------------------------------- #
@dataclass
class PlcConfig:
    ip: str = "192.168.1.250"
    port: int = 5000
    timeout: float = 3.0


# ---------------------------------------------------------------------- #
#  API MES                                                                #
# ---------------------------------------------------------------------- #
@dataclass
class ApiConfig:
    url: str = "http://localhost/api/mes/upload"
    timeout: float = 5.0
    retries: int = 3
    verify_ssl: bool = True
    # cách dựng trường "data": values_only | full_row | structured
    data_format: str = "values_only"
    # Proxy: MES nội bộ thường KHÔNG nên đi qua proxy công ty.
    #   use_proxy = False -> bỏ qua proxy hệ thống (mặc định)
    #   use_proxy = True  -> dùng proxy hệ thống, hoặc 'proxy' nếu có nhập
    use_proxy: bool = False
    proxy: str = ""          # vd "http://10.0.0.1:8080" (chỉ khi use_proxy=True)

    # --- Kiểm tra SN bằng GET TRƯỚC khi chạy ---
    # GET tới: check_url_prefix + SN + check_url_suffix
    # SN hợp lệ nếu nội dung trả về CHỨA chuỗi check_ok_contains.
    check_enabled: bool = True
    check_url_prefix: str = ""      # vd "http://mes/api/check?sn="
    check_url_suffix: str = ""      # vd "&station=OP10"
    check_ok_contains: str = "0"    # body CHỨA chuỗi này -> SN hợp lệ (theo mẫu)

    # --- Tiêu chí POST thành công ---
    # body CHỨA chuỗi này -> coi là POST thành công (để trống = dựa HTTP 2xx)
    post_ok_contains: str = "200"


# ---------------------------------------------------------------------- #
#  Đường dẫn file dữ liệu                                                 #
#    <base_dir>/<sub_8x>/<YYYYMMDD>/CCD1*  (bên trái)                     #
#    <base_dir>/<sub_8x>/<YYYYMMDD>/CCD2*  (bên phải)                     #
# ---------------------------------------------------------------------- #
@dataclass
class PathConfig:
    base_dir: str = "sample_data"
    sub_8x: str = "8X/data"
    sub_16x: str = "16X/data"
    left_glob: str = "CCD1*"
    right_glob: str = "CCD2*"
    # True  -> CHỈ đọc dữ liệu của ngày hôm nay; thiếu thì báo lỗi.
    # False -> lấy dữ liệu ở thư mục ngày mới nhất (cho phép ngày cũ).
    require_today: bool = True


# ---------------------------------------------------------------------- #
#  Toàn bộ cấu hình                                                       #
# ---------------------------------------------------------------------- #
@dataclass
class AppConfig:
    simulation: bool = True          # True = chạy giả lập, không cần phần cứng
    poll_interval_ms: int = 200      # chu kỳ đọc bit PLC
    handshake_timeout_s: float = 10.0  # thời gian chờ PLC nhả trigger sau khi done

    plc: PlcConfig = field(default_factory=PlcConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    left: SideConfig = field(default_factory=lambda: SideConfig(
        name="LEFT", ccd_prefix="CCD1", scanner_port="COM1",
        trig_8x="M100", done_8x="M101", trig_16x="M110", done_16x="M111"))
    right: SideConfig = field(default_factory=lambda: SideConfig(
        name="RIGHT", ccd_prefix="CCD2", scanner_port="COM2",
        trig_8x="M200", done_8x="M201", trig_16x="M210", done_16x="M211"))
    materials: List[MaterialConfig] = field(default_factory=list)


# ---------------------------------------------------------------------- #
#  Chuyển dict <-> dataclass (hỗ trợ lồng nhau)                          #
# ---------------------------------------------------------------------- #
def _from_dict(cls, data):
    """Dựng lại dataclass (kể cả lồng nhau / list) từ dict đã nạp JSON."""
    if not is_dataclass(cls):
        return data
    kwargs = {}
    type_hints = {f.name: f.type for f in fields(cls)}
    for f in fields(cls):
        if f.name not in data:
            continue
        val = data[f.name]
        hint = type_hints[f.name]
        if cls is AppConfig and f.name in ("plc", "api", "paths", "left", "right"):
            sub_cls = {"plc": PlcConfig, "api": ApiConfig, "paths": PathConfig,
                       "left": SideConfig, "right": SideConfig}[f.name]
            kwargs[f.name] = _from_dict(sub_cls, val)
        elif f.name == "materials":
            kwargs[f.name] = [_from_dict(MaterialConfig, m) for m in val]
        else:
            kwargs[f.name] = val
    return cls(**kwargs)


def load_config(path):
    """Nạp cấu hình từ JSON; nếu file chưa có thì trả về cấu hình mặc định."""
    if not os.path.exists(path):
        return AppConfig()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return _from_dict(AppConfig, data)


def save_config(cfg, path):
    """Lưu cấu hình ra JSON (UTF-8, giữ tiếng Việt)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, ensure_ascii=False, indent=2)


def side_addresses(side_cfg, head_type):
    """Trả về (trigger_bit, done_bit) theo loại đầu '8X' / '16X'."""
    if head_type == "8X":
        return side_cfg.trig_8x, side_cfg.done_8x
    return side_cfg.trig_16x, side_cfg.done_16x


def head_count(material, head_type):
    """Số đầu (số lần chạy) của 1 mã liệu theo loại đầu."""
    if material is None:
        return 0
    return material.heads_8x if head_type == "8X" else material.heads_16x
