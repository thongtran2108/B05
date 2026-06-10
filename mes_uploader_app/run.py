# -*- coding: utf-8 -*-
"""Điểm chạy phần mềm MES Uploader (giao diện PySide6).

    python run.py

Lần đầu chạy, nếu chưa có config.json sẽ tạo cấu hình mặc định kèm 2 mã
liệu ví dụ (ABC, BCD) và bật chế độ GIẢ LẬP để thử ngay không cần phần cứng.
"""

import os
import sys

from mes_uploader.config import (
    load_config, save_config, MaterialConfig,
)


def _app_dir():
    """Thư mục gốc của ứng dụng.

    - Khi đóng gói thành .exe (PyInstaller): trả về thư mục CHỨA file .exe để
      config.json / sample_data nằm CẠNH exe (giữ được sau mỗi lần chạy, dễ sửa).
    - Khi chạy mã nguồn (python run.py): trả về thư mục chứa run.py.
    """
    if getattr(sys, "frozen", False):       # đang chạy từ bản đóng gói
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _resource(rel):
    """Đường dẫn tài nguyên đóng gói (vd icon): trong _MEIPASS khi đã đóng gói,
    cạnh run.py khi chạy mã nguồn."""
    base = getattr(sys, "_MEIPASS", "") or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel)


CONFIG_PATH = os.path.join(_app_dir(), "config.json")


def _seed_if_empty(cfg):
    """Tạo dữ liệu mẫu cho lần chạy đầu (chưa có mã liệu)."""
    if not cfg.materials:
        cfg.materials = [
            MaterialConfig("ABC", heads_8x=2, heads_16x=1),
            MaterialConfig("BCD", heads_8x=4, heads_16x=1),
        ]
        # trỏ thư mục dữ liệu mẫu kèm theo project (nếu có)
        sample = os.path.join(os.path.dirname(CONFIG_PATH), "sample_data")
        if os.path.isdir(sample):
            cfg.paths.base_dir = sample
        save_config(cfg, CONFIG_PATH)
    return cfg


def main():
    cfg = _seed_if_empty(load_config(CONFIG_PATH))

    # import Qt muộn để các test/headless không cần PySide6
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from mes_uploader.ui.main_window import MainWindow
    from mes_uploader.ui.theme import apply_dark_theme

    app = QApplication(sys.argv)
    icon_path = _resource(os.path.join("assets", "ninja.png"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))   # icon cửa sổ + thanh tác vụ
    apply_dark_theme(app)
    win = MainWindow(cfg, CONFIG_PATH)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
