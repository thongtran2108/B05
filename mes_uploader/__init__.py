# -*- coding: utf-8 -*-
"""Phần mềm tải nội dung đo lên hệ thống MES qua API.

Gồm 2 bên Trái / Phải hoạt động độc lập nhưng cùng một lưu trình:
  Quét SN -> chờ tín hiệu chạy từ PLC (Mitsubishi) -> lấy dòng dữ liệu
  mới nhất trong file (CSV/Excel) -> bắt tay 'done' về PLC -> lặp đủ số
  đầu (8X / 16X theo mã liệu) -> gộp dữ liệu -> POST lên MES.
"""

__version__ = "0.1.0"
