# -*- coding: utf-8 -*-
"""Ghi nhật ký quét mã / tải MES ra FILE theo ngày (để truy vết sự cố).

Mỗi dòng: [YYYY-MM-DD HH:MM:SS] [CCD1] <nội dung>

- Ghi đủ: trạng thái quét mã (OK/chặn), từng đầu đo, dữ liệu (timer) đã gửi
  lên MES và phản hồi của MES (mã HTTP + nội dung trả về).
- File: <log_dir>/scan_YYYYMMDD.log (log_dir trống = thư mục 'logs' cạnh app).
- An toàn nhiều luồng (2 bên ghi chung 1 file) và KHÔNG bao giờ ném lỗi ra
  ngoài: ghi log hỏng cũng không được làm chết worker.

Dùng dạng singleton cấp module: configure() 1 lần lúc khởi động (và mỗi lần
đổi Setting), rồi log() ở bất cứ đâu.
"""

import datetime
import os
import sys
import threading

_lock = threading.Lock()
_dir = ""
_enabled = False


def default_log_dir():
    """Thư mục log mặc định = 'logs' cạnh ứng dụng (exe hoặc thư mục chứa run.py)."""
    if getattr(sys, "frozen", False):           # bản đóng gói PyInstaller
        base = os.path.dirname(sys.executable)
    else:                                        # chạy mã nguồn: .../mes_uploader_app
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "logs")


def resolve_log_dir(cfg):
    """Thư mục log từ cấu hình: cfg.log_dir nếu có, ngược lại mặc định."""
    d = (getattr(cfg, "log_dir", "") or "").strip()
    return d or default_log_dir()


def configure(log_dir, enabled):
    """Bật/tắt + đặt thư mục ghi log. Gọi lúc khởi động và khi đổi Setting."""
    global _dir, _enabled
    with _lock:
        _dir = (log_dir or "").strip() or default_log_dir()
        _enabled = bool(enabled)


def configure_from(cfg):
    """Tiện ích: cấu hình theo AppConfig."""
    configure(resolve_log_dir(cfg), getattr(cfg, "log_enabled", True))


def is_enabled():
    return _enabled


def _path_for(when):
    return os.path.join(_dir, "scan_%s.log" % when.strftime("%Y%m%d"))


def log(side, text):
    """Ghi 1 dòng log (kèm thời gian + nhãn bên). Bỏ qua im lặng nếu tắt/lỗi."""
    if not _enabled or not text:
        return
    now = datetime.datetime.now()
    line = "[%s] [%s] %s\n" % (now.strftime("%Y-%m-%d %H:%M:%S"), side, text)
    try:
        with _lock:
            os.makedirs(_dir, exist_ok=True)
            with open(_path_for(now), "a", encoding="utf-8") as f:
                f.write(line)
    except Exception:                            # noqa: BLE001 (log hỏng không làm chết app)
        pass
