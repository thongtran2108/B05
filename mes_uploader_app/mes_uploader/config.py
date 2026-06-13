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
#  Mã liệu: thuộc 1 chuyên án, mỗi mã có số đầu 4X / 8X / 16X khác nhau   #
#  (mã có thể chỉ dùng 1 vài loại đầu — số đầu = 0 nghĩa là không có).    #
#  "project" (chuyên án) dùng để gom nhóm mã liệu: mỗi chuyên án có danh  #
#  sách mã liệu riêng; cùng tên mã liệu có thể nằm ở các chuyên án khác   #
#  nhau. Bỏ trống project = nhóm chung (tương thích cấu hình cũ).         #
# ---------------------------------------------------------------------- #
@dataclass
class MaterialConfig:
    name: str = ""          # tên mã liệu, vd "ABC"
    project: str = ""       # chuyên án chứa mã liệu này (gom nhóm mã liệu)
    heads_4x: int = 0       # số đầu 4X  -> số lần chạy khi chọn 4X
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
    trig_4x: str = "M120"
    done_4x: str = "M121"
    trig_8x: str = "M100"
    done_8x: str = "M101"
    trig_16x: str = "M110"
    done_16x: str = "M111"

    # Thanh ghi (word) ghi KẾT QUẢ kiểm tra SN về PLC: 1 = OK, 2 = NG.
    # vd "D100". Để trống = không ghi.
    sn_result_reg: str = ""

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
    # Giao thức: "slmp" (Mitsubishi MC/SLMP, mặc định) hoặc "modbus" (Modbus/TCP).
    protocol: str = "slmp"
    # Communication Data Code của SLMP: False = Binary (mặc định), True = ASCII.
    ascii_mode: bool = False
    modbus_unit: int = 255           # Unit ID khi dùng Modbus/TCP (FX5U: thường 255)


# ---------------------------------------------------------------------- #
#  API MES                                                                #
# ---------------------------------------------------------------------- #
@dataclass
class HeadApiConfig:
    """API riêng cho 1 loại đầu (4X / 8X / 16X).

    Gồm endpoint POST (tải kết quả) + GET kiểm tra SN + tiêu chí OK. Chọn loại
    đầu nào thì worker chạy theo đúng API này. Các tham số kết nối (timeout,
    retry, SSL, proxy, định dạng data) dùng CHUNG ở ApiConfig.
    """
    url: str = "http://localhost/api/mes/upload"   # POST tải kết quả
    # body CHỨA chuỗi này -> coi là POST thành công (để trống = dựa HTTP 2xx)
    post_ok_contains: str = "200"
    # Tên trạm gửi trong body POST ("stationName"). Mỗi loại đầu 4X/8X/16X có
    # 1 tên trạm khác nhau -> đặt riêng cho từng HeadApiConfig.
    station_name: str = ""

    # --- Kiểm tra SN bằng GET TRƯỚC khi chạy ---
    # GET tới: check_url_prefix + SN + check_url_suffix
    # SN hợp lệ khi nội dung trả về BẰNG ĐÚNG check_ok_value (giống main.py:
    # req.text == '0'). Để trống check_ok_value -> chỉ cần HTTP 2xx.
    check_enabled: bool = True
    check_url_prefix: str = ""      # vd "http://mes/api/check?sn="
    check_url_suffix: str = ""      # vd "&station=OP10"
    check_ok_value: str = "0"       # body == giá trị này -> SN hợp lệ (vd "0")


@dataclass
class ApiConfig:
    timeout: float = 5.0
    retries: int = 3
    verify_ssl: bool = True
    # Mã nhân viên gửi trong body POST ("empNo") — dùng chung cho mọi loại đầu.
    emp_no: str = "V3081479"
    # Proxy: MES nội bộ thường KHÔNG nên đi qua proxy công ty.
    #   use_proxy = False -> bỏ qua proxy hệ thống (mặc định)
    #   use_proxy = True  -> dùng proxy hệ thống, hoặc 'proxy' nếu có nhập
    use_proxy: bool = False
    proxy: str = ""          # vd "http://10.0.0.1:8080" (chỉ khi use_proxy=True)
    # Tải trường "timer" (toàn bộ giá trị đo) lên MES hay không.
    #   True  -> body có "timer" (mặc định)
    #   False -> KHÔNG gửi "timer" (chỉ sn + stationName + empNo)
    upload_timer: bool = True

    # --- API riêng theo loại đầu: chọn đầu nào sẽ chạy theo API tương ứng ---
    api_4x: HeadApiConfig = field(default_factory=HeadApiConfig)
    api_8x: HeadApiConfig = field(default_factory=HeadApiConfig)
    api_16x: HeadApiConfig = field(default_factory=HeadApiConfig)


# ---------------------------------------------------------------------- #
#  Đường dẫn file dữ liệu                                                 #
#    <base_dir>/<sub_4x|sub_8x|sub_16x>/<YYYYMMDD>/CCD1*  (bên trái)      #
#    <base_dir>/<sub_4x|sub_8x|sub_16x>/<YYYYMMDD>/CCD2*  (bên phải)      #
# ---------------------------------------------------------------------- #
@dataclass
class PathConfig:
    base_dir: str = "sample_data"
    sub_4x: str = "4X/data"
    sub_8x: str = "8X/data"
    sub_16x: str = "16X/data"
    left_glob: str = "CCD1*"
    right_glob: str = "CCD2*"
    # True  -> CHỈ đọc dữ liệu của ngày hôm nay; thiếu thì báo lỗi.
    # False -> lấy dữ liệu ở thư mục ngày mới nhất (cho phép ngày cũ).
    require_today: bool = True


# ---------------------------------------------------------------------- #
#  Tải ảnh AOI lên link mạng (copy file sang thư mục chia sẻ)            #
#    Nguồn ở máy (riêng theo loại đầu):                                   #
#      <source_dir>/<sub_image>/<YYYY-MM-DD>/<OK|NG>/  -> các file ảnh    #
#    Đích (riêng theo loại đầu): <upload_dir>/<YYYYMMDD>/                  #
#  Nhận OK/NG của 1 đầu -> lấy ảnh MỚI NHẤT trong thư mục OK|NG tương ứng #
#  rồi copy lên đích, đổi tên: <SN>_<YYYYMMDD HHMMSS>_Passed|Failed.<ext> #
# ---------------------------------------------------------------------- #
@dataclass
class HeadImageConfig:
    """Đường dẫn ảnh cho 1 loại đầu (4X / 8X / 16X)."""
    source_dir: str = ""    # thư mục gốc ở máy chứa ảnh của loại đầu này
    upload_dir: str = ""    # link đích để tải (copy) ảnh lên (vd UNC //host/share)


@dataclass
class ImageConfig:
    enabled: bool = True
    sub_image: str = "Image"        # thư mục con chứa ảnh theo ngày
    ok_dir: str = "OK"              # thư mục ảnh khi kết quả OK
    ng_dir: str = "NG"             # thư mục ảnh khi kết quả NG
    # các phần mở rộng ảnh sẽ tìm Ở NGUỒN (không phân biệt hoa/thường).
    # Ảnh TẢI LÊN luôn được lưu dạng .jpg nén (xem image_uploader).
    extensions: List[str] = field(
        default_factory=lambda: [".jpg", ".jpeg", ".png", ".bmp"])
    # Mức nén JPG (1..100) khi PHẢI chuyển ảnh nguồn (PNG/BMP…) sang .jpg.
    # Ảnh nguồn vốn là .jpg sẽ được giữ nguyên (không nén lại, tránh giảm chất lượng).
    jpeg_quality: int = 85
    # API riêng theo loại đầu: chọn đầu nào sẽ tải ảnh theo đường dẫn tương ứng
    img_4x: HeadImageConfig = field(default_factory=HeadImageConfig)
    img_8x: HeadImageConfig = field(default_factory=HeadImageConfig)
    img_16x: HeadImageConfig = field(default_factory=HeadImageConfig)


# ---------------------------------------------------------------------- #
#  Lưu giá trị đo ra Excel (.xlsx) — kèm cột SN                           #
#    SAO CHÉP nguyên file đo gốc (GIỮ công thức + màu tô) rồi THÊM cột SN  #
#    ở cuối; đóng dấu SN vào đúng dòng vừa đọc (khớp theo cột Time).      #
#    Mỗi loại đầu 4X / 8X / 16X có 1 THƯ MỤC LƯU RIÊNG.                   #
#    File: <output_dir_*>/<YYYYMMDD>/<tên file đo gốc>.xlsx               #
# ---------------------------------------------------------------------- #
@dataclass
class ExcelConfig:
    # Mặc định TẮT (opt-in): bật trong Setting để bắt đầu ghi .xlsx ra đĩa.
    enabled: bool = False
    # Thư mục lưu CHUNG (dự phòng): dùng khi thư mục riêng theo đầu để trống.
    # Để trống tất cả = thư mục 'excel_data' cạnh ứng dụng.
    output_dir: str = ""
    # Thư mục lưu RIÊNG cho từng loại đầu (trống -> lùi về output_dir chung).
    output_dir_4x: str = ""
    output_dir_8x: str = ""
    output_dir_16x: str = ""


# ---------------------------------------------------------------------- #
#  Toàn bộ cấu hình                                                       #
# ---------------------------------------------------------------------- #
@dataclass
class AppConfig:
    language: str = "vi"             # ngôn ngữ giao diện: "vi" | "zh" | "en"
    simulation: bool = True          # True = PLC giả lập (Mock), không cần phần cứng
    # True = nhập SN bằng tay (ô text + nút Quét) thay vì tay scan COM.
    # simulation=False + manual_sn=True => chế độ "PLC thật + nhập SN tay".
    manual_sn: bool = False
    poll_interval_ms: int = 200      # chu kỳ đọc bit PLC

    # Lưu nhật ký (quét mã, dữ liệu tải lên, phản hồi MES) ra file theo ngày.
    #   log_enabled = True  -> ghi file logs/scan_YYYYMMDD.log
    #   log_dir            -> thư mục log (để trống = thư mục 'logs' cạnh ứng dụng)
    log_enabled: bool = True
    log_dir: str = ""

    plc: PlcConfig = field(default_factory=PlcConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    images: ImageConfig = field(default_factory=ImageConfig)
    excel: ExcelConfig = field(default_factory=ExcelConfig)
    left: SideConfig = field(default_factory=lambda: SideConfig(
        name="LEFT", ccd_prefix="CCD1", scanner_port="COM1",
        trig_4x="M120", done_4x="M121",
        trig_8x="M100", done_8x="M101", trig_16x="M110", done_16x="M111"))
    right: SideConfig = field(default_factory=lambda: SideConfig(
        name="RIGHT", ccd_prefix="CCD2", scanner_port="COM2",
        trig_4x="M220", done_4x="M221",
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
        if cls is AppConfig and f.name == "api":
            kwargs[f.name] = _api_from_dict(val)
        elif cls is AppConfig and f.name == "images":
            kwargs[f.name] = _images_from_dict(val)
        elif cls is AppConfig and f.name in ("plc", "paths", "left", "right", "excel"):
            sub_cls = {"plc": PlcConfig, "paths": PathConfig, "left": SideConfig,
                       "right": SideConfig, "excel": ExcelConfig}[f.name]
            kwargs[f.name] = _from_dict(sub_cls, val)
        elif f.name == "materials":
            kwargs[f.name] = [_from_dict(MaterialConfig, m) for m in val]
        else:
            kwargs[f.name] = val
    return cls(**kwargs)


def _legacy_head_api(data):
    """Lấy HeadApiConfig từ các trường API 'phẳng' kiểu cũ (1 API chung)."""
    kwargs = {}
    for name in ("url", "post_ok_contains", "station_name", "check_enabled",
                 "check_url_prefix", "check_url_suffix", "check_ok_value"):
        if name in data:
            kwargs[name] = data[name]
    # tương thích khóa cũ 'check_ok_contains' (nay đổi thành 'check_ok_value')
    if "check_ok_value" not in data and "check_ok_contains" in data:
        kwargs["check_ok_value"] = data["check_ok_contains"]
    return HeadApiConfig(**kwargs)


def _head_api_from_dict(sub):
    """HeadApiConfig từ 1 sub-dict 'api_*' mới, tương thích khóa cũ.

    Cấu hình cũ dùng 'check_ok_contains' (so khớp 'chứa'); nay đổi thành
    'check_ok_value' (so khớp BẰNG ĐÚNG như main.py) -> tự chuyển khi nạp.
    """
    cfg = _from_dict(HeadApiConfig, sub)
    if "check_ok_value" not in sub and "check_ok_contains" in sub:
        cfg.check_ok_value = sub["check_ok_contains"]
    return cfg


def _api_from_dict(data):
    """Dựng ApiConfig từ dict, hỗ trợ 2 dạng:

      - MỚI: có api_4x / api_8x / api_16x (mỗi đầu 1 HeadApiConfig riêng).
      - CŨ : các trường url / check_* / post_ok_contains nằm thẳng trong 'api'
             (1 API chung) -> tự nhân ra cho cả 3 loại đầu (mỗi đầu 1 bản độc
             lập) để giữ nguyên hành vi khi nâng cấp.
    """
    if not isinstance(data, dict):
        return ApiConfig()
    shared = {}
    for f in fields(ApiConfig):
        if f.name in ("api_4x", "api_8x", "api_16x"):
            continue
        if f.name in data:
            shared[f.name] = data[f.name]
    heads = {}
    for fld in ("api_4x", "api_8x", "api_16x"):
        sub = data.get(fld)
        heads[fld] = (_head_api_from_dict(sub) if isinstance(sub, dict)
                      else _legacy_head_api(data))
    return ApiConfig(**shared, **heads)


def _images_from_dict(data):
    """Dựng ImageConfig từ dict; mỗi loại đầu 1 HeadImageConfig riêng.

    Cấu hình cũ (không có 'images') -> bên gọi dùng ImageConfig() mặc định.
    """
    if not isinstance(data, dict):
        return ImageConfig()
    shared = {}
    for f in fields(ImageConfig):
        if f.name in ("img_4x", "img_8x", "img_16x"):
            continue
        if f.name in data:
            shared[f.name] = data[f.name]
    heads = {}
    for fld in ("img_4x", "img_8x", "img_16x"):
        sub = data.get(fld)
        heads[fld] = (_from_dict(HeadImageConfig, sub) if isinstance(sub, dict)
                      else HeadImageConfig())
    return ImageConfig(**shared, **heads)


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
    """Trả về (trigger_bit, done_bit) theo loại đầu '4X' / '8X' / '16X'."""
    if head_type == "4X":
        return side_cfg.trig_4x, side_cfg.done_4x
    if head_type == "8X":
        return side_cfg.trig_8x, side_cfg.done_8x
    return side_cfg.trig_16x, side_cfg.done_16x


def head_count(material, head_type):
    """Số đầu (số lần chạy) của 1 mã liệu theo loại đầu."""
    if material is None:
        return 0
    if head_type == "4X":
        return material.heads_4x
    if head_type == "8X":
        return material.heads_8x
    return material.heads_16x


def head_api(api_cfg, head_type):
    """Trả về HeadApiConfig (API riêng) theo loại đầu '4X' / '8X' / '16X'."""
    if head_type == "4X":
        return api_cfg.api_4x
    if head_type == "8X":
        return api_cfg.api_8x
    return api_cfg.api_16x


def head_image(images_cfg, head_type):
    """Trả về HeadImageConfig (đường dẫn ảnh) theo loại đầu '4X' / '8X' / '16X'."""
    if head_type == "4X":
        return images_cfg.img_4x
    if head_type == "8X":
        return images_cfg.img_8x
    return images_cfg.img_16x


def manual_sn_entry(cfg):
    """SN nhập bằng tay (ô text + nút Quét) thay vì tay scan COM?

    Đúng khi: chế độ giả lập, HOẶC bật 'nhập SN tay' (PLC thật + SN tay).
    """
    return bool(cfg.simulation or getattr(cfg, "manual_sn", False))


def app_mode(cfg):
    """Chế độ chạy: 'sim' (giả lập) | 'manual_sn' (PLC thật + SN tay) | 'live' (thật)."""
    if cfg.simulation:
        return "sim"
    return "manual_sn" if getattr(cfg, "manual_sn", False) else "live"
