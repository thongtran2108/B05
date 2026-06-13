#!/usr/bin/env bash
# ============================================================================
#  Đóng gói MES Uploader bằng PyInstaller.
#  LƯU Ý: PyInstaller KHÔNG cross-compile — chạy script này trên Linux/macOS
#  chỉ tạo file chạy CHO CHÍNH HỆ ĐIỀU HÀNH ĐÓ (để TEST cấu hình đóng gói).
#  Muốn ra .exe Windows: chạy build_exe.bat TRÊN WINDOWS.
# ============================================================================
set -e
cd "$(dirname "$0")"

echo "=== [1/3] Cài dependencies + PyInstaller ==="
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt

echo "=== [2/3] Đóng gói (onefile, windowed) ==="
python -m PyInstaller --noconfirm --clean --onefile --windowed \
  --name MES_Uploader \
  --icon assets/ninja.ico \
  --add-data "assets/ninja.png:assets" \
  --hidden-import openpyxl --hidden-import serial --hidden-import requests \
  --hidden-import PIL --hidden-import PIL.Image \
  --exclude-module tkinter --exclude-module numpy --exclude-module cv2 \
  --exclude-module matplotlib --exclude-module pandas \
  --exclude-module cryptography \
  run.py

echo "=== [3/3] Chép dữ liệu mẫu + cấu hình mẫu cạnh file chạy ==="
[ -d sample_data ] && cp -r sample_data dist/sample_data || true
[ -f config.example.json ] && cp -f config.example.json dist/config.example.json || true

echo "Xong: dist/MES_Uploader (cho HỆ ĐIỀU HÀNH HIỆN TẠI — KHÔNG phải .exe Windows)"
