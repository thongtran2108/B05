@echo off
REM ============================================================================
REM  Dong goi MES Uploader thanh 1 file .exe (PyInstaller) - CHAY TREN WINDOWS.
REM  Yeu cau: da cai Python 3.9+ (tich "Add Python to PATH" khi cai).
REM  Cach dung: bam doi chuot vao file nay, hoac chay trong cmd:  build_exe.bat
REM  Ket qua:  dist\MES_Uploader.exe  (kem sample_data\ + config.example.json)
REM ============================================================================
setlocal
cd /d "%~dp0"

echo.
echo === [1/3] Cai dependencies + PyInstaller ===
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt
if errorlevel 1 ( echo [LOI] Cai dependencies that bai. & pause & exit /b 1 )

echo.
echo === [2/3] Dong goi (1 file .exe, khong console) ===
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name MES_Uploader ^
  --hidden-import openpyxl --hidden-import serial --hidden-import requests ^
  --exclude-module tkinter --exclude-module numpy --exclude-module cv2 ^
  --exclude-module matplotlib --exclude-module PIL --exclude-module pandas ^
  --exclude-module cryptography ^
  run.py
if errorlevel 1 ( echo [LOI] Dong goi that bai. & pause & exit /b 1 )

echo.
echo === [3/3] Chep du lieu mau + cau hinh mau canh exe ===
if exist sample_data xcopy /E /I /Y sample_data "dist\sample_data" >nul
if exist config.example.json copy /Y config.example.json "dist\config.example.json" >nul

echo.
echo ============================================================================
echo  XONG! File chay: dist\MES_Uploader.exe
echo  - Copy ca thu muc "dist" sang may chay (exe + sample_data + config.example.json).
echo  - Lan dau chay se tu tao config.json CANH exe; vao Setting de chinh duong dan.
echo ============================================================================
pause
endlocal
