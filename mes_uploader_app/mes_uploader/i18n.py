# -*- coding: utf-8 -*-
"""Đa ngôn ngữ (i18n) cho toàn ứng dụng: Tiếng Việt / 中文 / English.

Cách dùng kiểu gettext: CHUỖI NGUỒN TIẾNG VIỆT chính là KHÓA. Hàm tr(text)
trả về bản dịch theo ngôn ngữ đang chọn; nếu chưa có bản dịch (hoặc đang ở
tiếng Việt) thì trả về nguyên chuỗi nguồn. Nhờ vậy mã nguồn vẫn đọc được
(thấy tiếng Việt trực tiếp) và chỉ cần bổ sung bảng dịch cho 'en' / 'zh'.

Chuỗi có tham số dùng %-format: dịch xong mới format, ví dụ
    tr("Đã bật. Chờ quét mã (loại %s).") % head_type
Các bản dịch PHẢI giữ nguyên số lượng và thứ tự ký tự %s / %d.

Đổi ngôn ngữ lúc đang chạy: set_language(code) sẽ gọi lại tất cả listener đã
đăng ký (các cửa sổ tự cập nhật văn bản — retranslate). Module này KHÔNG phụ
thuộc PySide6 để phần lõi/worker và test headless vẫn import được.
"""

# (mã, nhãn hiển thị) — nhãn luôn ở dạng bản ngữ của chính ngôn ngữ đó.
LANGUAGES = [("vi", "Tiếng Việt"), ("zh", "中文"), ("en", "English")]
DEFAULT_LANGUAGE = "vi"

_LANG_CODES = {code for code, _ in LANGUAGES}

_state = {"lang": DEFAULT_LANGUAGE}
_listeners = []          # các hàm gọi lại khi đổi ngôn ngữ (retranslate)


# ---------------------------------------------------------------------- #
#  Bảng dịch: { "chuỗi nguồn tiếng Việt": {"en": ..., "zh": ...} }        #
#  Thiếu khóa / thiếu ngôn ngữ -> tự lùi về chuỗi nguồn (tiếng Việt).     #
# ---------------------------------------------------------------------- #
_TR = {
    # ----- Cửa sổ chính / header -----
    "MES Uploader — Tải nội dung đo lên MES": {
        "en": "MES Uploader — Upload measurement data to MES",
        "zh": "MES 上传工具 — 上传测量数据到 MES",
    },
    "Tải nội dung đo lên hệ thống MES": {
        "en": "Upload measurement data to the MES system",
        "zh": "上传测量数据到 MES 系统",
    },
    "Setting": {"en": "Settings", "zh": "设置"},
    "OK": {"en": "OK", "zh": "确定"},
    "Hủy": {"en": "Cancel", "zh": "取消"},
    "Chế độ GIẢ LẬP": {"en": "SIMULATION mode", "zh": "模拟模式"},
    "Chế độ THẬT (PLC + scan)": {
        "en": "LIVE mode (PLC + scan)", "zh": "实机模式 (PLC + 扫码)"},
    "Chế độ PLC THẬT + SN tay": {
        "en": "REAL PLC + manual SN mode", "zh": "真实 PLC + 手动 SN 模式"},
    "Lưu cấu hình": {"en": "Save configuration", "zh": "保存配置"},
    "Không lưu được file cấu hình:\n%s": {
        "en": "Could not save the configuration file:\n%s",
        "zh": "无法保存配置文件：\n%s",
    },
    "Đã lưu cấu hình. Bấm 'Bắt đầu' lại ở mỗi bên để áp dụng.": {
        "en": "Configuration saved. Press 'Start' again on each side to apply.",
        "zh": "配置已保存。请在每一侧重新点击“开始”以生效。",
    },

    # ----- Panel 1 bên -----
    "BÊN TRÁI · CCD1": {"en": "LEFT · CCD1", "zh": "左侧 · CCD1"},
    "BÊN PHẢI · CCD2": {"en": "RIGHT · CCD2", "zh": "右侧 · CCD2"},
    "CHUYÊN ÁN": {"en": "PROJECT", "zh": "专案"},
    "MÃ LIỆU": {"en": "MATERIAL", "zh": "料号"},
    "LOẠI ĐẦU": {"en": "HEAD TYPE", "zh": "探头类型"},
    "TIẾN ĐỘ ĐẦU ĐO": {"en": "HEAD PROGRESS", "zh": "探头进度"},
    "SERIAL NUMBER": {"en": "SERIAL NUMBER", "zh": "序列号"},
    "BẢNG DỮ LIỆU": {"en": "DATA TABLE", "zh": "数据表"},
    "NHẬT KÝ": {"en": "LOG", "zh": "日志"},
    "Bắt đầu": {"en": "Start", "zh": "开始"},
    "Dừng": {"en": "Stop", "zh": "停止"},
    "Quét (giả lập)": {"en": "Scan (sim)", "zh": "扫码 (模拟)"},
    "Tín hiệu PLC (giả lập)": {"en": "PLC signal (sim)", "zh": "PLC 信号 (模拟)"},
    "Xóa bảng": {"en": "Clear table", "zh": "清空表格"},
    "Nhập SN giả lập…": {"en": "Enter simulated SN…", "zh": "输入模拟 SN…"},
    "(Chung)": {"en": "(Common)", "zh": "(通用)"},
    "Trạng thái": {"en": "Status", "zh": "状态"},
    "chưa bật": {"en": "not started", "zh": "未启动"},
    "chờ quét mã": {"en": "waiting for scan", "zh": "等待扫码"},
    "đang chạy": {"en": "running", "zh": "运行中"},
    "đã dừng": {"en": "stopped", "zh": "已停止"},
    "kết nối": {"en": "connected", "zh": "已连接"},
    "mất kết nối": {"en": "disconnected", "zh": "连接断开"},
    "LỖI DỮ LIỆU": {"en": "DATA ERROR", "zh": "数据错误"},
    "SN BỊ CHẶN": {"en": "SN BLOCKED", "zh": "SN 被拦截"},
    "LỖI": {"en": "ERROR", "zh": "错误"},
    "CHẶN": {"en": "BLOCKED", "zh": "拦截"},
    "(gửi lỗi)": {"en": "(send failed)", "zh": "(发送失败)"},
    "Loại": {"en": "Type", "zh": "类型"},
    "Đầu": {"en": "Head", "zh": "探头"},
    "Judge": {"en": "Judge", "zh": "判定"},
    "Thời gian": {"en": "Time", "zh": "时间"},
    "Giá trị (Data01..N)": {"en": "Values (Data01..N)", "zh": "数值 (Data01..N)"},
    "%d giá trị:\n%s": {"en": "%d values:\n%s", "zh": "%d 个数值：\n%s"},
    "Đã gửi MES (result=%s)": {
        "en": "Sent to MES (result=%s)", "zh": "已发送 MES (result=%s)"},
    "Gửi MES lỗi — xem nhật ký": {
        "en": "MES send failed — see log", "zh": "MES 发送失败 — 请查看日志"},
    "Chưa chọn mã liệu. Vào Setting > Mã liệu để thêm.": {
        "en": "No material selected. Go to Settings > Materials to add one.",
        "zh": "未选择料号。请到 设置 > 料号 添加。",
    },
    "Mã liệu '%s' không có đầu %s.": {
        "en": "Material '%s' has no %s head.", "zh": "料号 '%s' 没有 %s 探头。"},
    "Chưa bấm 'Bắt đầu'.": {
        "en": "'Start' has not been pressed.", "zh": "尚未点击“开始”。"},

    # ----- Worker (nhật ký / trạng thái chạy) -----
    "Đang chạy — không đổi được lựa chọn.": {
        "en": "Running — selection cannot be changed.",
        "zh": "运行中 — 无法更改选择。",
    },
    "Đã bật. Chờ quét mã (loại %s).": {
        "en": "Started. Waiting for scan (type %s).",
        "zh": "已启动。等待扫码 (类型 %s)。",
    },
    "Đã dừng.": {"en": "Stopped.", "zh": "已停止。"},
    "Bỏ qua mã '%s' (chưa sẵn sàng quét).": {
        "en": "Skipped code '%s' (not ready to scan).",
        "zh": "已忽略条码 '%s' (尚未准备好扫码)。",
    },
    "Mã liệu '%s' không có đầu %s — bỏ qua SN %s.": {
        "en": "Material '%s' has no %s head — skipping SN %s.",
        "zh": "料号 '%s' 没有 %s 探头 — 跳过 SN %s。",
    },
    "  (Bỏ qua kiểm tra SN: chưa cấu hình URL GET cho đầu %s)": {
        "en": "  (Skipping SN check: no GET URL configured for %s head)",
        "zh": "  (跳过 SN 检查：%s 探头未配置 GET 网址)",
    },
    "Kiểm tra SN %s qua GET (API đầu %s)…": {
        "en": "Checking SN %s via GET (%s head API)…",
        "zh": "通过 GET 检查 SN %s (%s 探头 API)…",
    },
    "  SN hợp lệ — cho phép chạy.": {
        "en": "  SN valid — allowed to run.", "zh": "  SN 有效 — 允许运行。"},
    "  [CHẶN] SN %s không hợp lệ: %s": {
        "en": "  [BLOCKED] SN %s invalid: %s", "zh": "  [拦截] SN %s 无效：%s"},
    "  → Vui lòng quét mã khác.": {
        "en": "  → Please scan a different code.", "zh": "  → 请扫描其它条码。"},
    "SN %s bị chặn: %s": {"en": "SN %s blocked: %s", "zh": "SN %s 被拦截：%s"},
    "SN %s — chờ tín hiệu PLC (0/%d đầu %s)": {
        "en": "SN %s — waiting for PLC signal (0/%d %s heads)",
        "zh": "SN %s — 等待 PLC 信号 (0/%d 个 %s 探头)",
    },
    "── Bắt đầu SN %s | mã liệu %s | %d đầu %s ──": {
        "en": "── Start SN %s | material %s | %d %s heads ──",
        "zh": "── 开始 SN %s | 料号 %s | %d 个 %s 探头 ──",
    },
    "Nhận tín hiệu chạy — đầu %d/%d": {
        "en": "Run signal received — head %d/%d",
        "zh": "收到运行信号 — 探头 %d/%d",
    },
    "  Đọc %s: judge=%s, %d giá trị": {
        "en": "  Read %s: judge=%s, %d values",
        "zh": "  读取 %s: judge=%s, %d 个数值",
    },
    "  [LỖI] %s": {"en": "  [ERROR] %s", "zh": "  [错误] %s"},
    "  → Hủy SN %s, KHÔNG tải lên MES. Vui lòng kiểm tra dữ liệu.": {
        "en": "  → Cancelling SN %s, NOT uploading to MES. Please check the data.",
        "zh": "  → 取消 SN %s，不上传到 MES。请检查数据。",
    },
    "LỖI thiếu dữ liệu — đã hủy SN %s. Chờ quét mã tiếp theo.": {
        "en": "Missing-data ERROR — cancelled SN %s. Waiting for next scan.",
        "zh": "数据缺失错误 — 已取消 SN %s。等待下一次扫码。",
    },
    "Đủ %d đầu → POST MES (API đầu %s): sn=%s, result=%s": {
        "en": "All %d heads done → POST MES (%s head API): sn=%s, result=%s",
        "zh": "已满 %d 个探头 → POST MES (%s 探头 API)：sn=%s, result=%s",
    },
    "  [OK] MES nhận OK (HTTP %s)": {
        "en": "  [OK] MES accepted (HTTP %s)", "zh": "  [OK] MES 接收成功 (HTTP %s)"},
    "  [FAIL] MES THẤT BẠI: %s": {
        "en": "  [FAIL] MES FAILED: %s", "zh": "  [FAIL] MES 失败：%s"},
    "Hoàn tất SN %s. Chờ quét mã tiếp theo.": {
        "en": "SN %s completed. Waiting for next scan.",
        "zh": "SN %s 完成。等待下一次扫码。",
    },
    "Chế độ GIẢ LẬP — không cần PLC/scan thật.": {
        "en": "SIMULATION mode — no real PLC/scanner needed.",
        "zh": "模拟模式 — 无需真实 PLC/扫码枪。",
    },
    "PLC kết nối OK (%s:%s).": {
        "en": "PLC connected OK (%s:%s).", "zh": "PLC 连接成功 (%s:%s)。"},
    "Không kết nối được PLC: %s": {
        "en": "Could not connect to PLC: %s", "zh": "无法连接 PLC：%s"},
    "Lỗi đọc PLC %s: %s": {
        "en": "PLC read error %s: %s", "zh": "PLC 读取错误 %s：%s"},
    "Lỗi ghi PLC %s: %s": {
        "en": "PLC write error %s: %s", "zh": "PLC 写入错误 %s：%s"},
    "Lỗi vòng lặp worker: %s": {
        "en": "Worker loop error: %s", "zh": "工作循环出错：%s"},
    "  [ẢNH] %s": {"en": "  [IMAGE] %s", "zh": "  [图片] %s"},
    "  [ẢNH] Bỏ qua: %s": {
        "en": "  [IMAGE] Skipped: %s", "zh": "  [图片] 跳过：%s"},
    "  [ẢNH] Bỏ qua: hàng đợi tải ảnh đầy (đích chậm?)": {
        "en": "  [IMAGE] Skipped: upload queue full (slow destination?)",
        "zh": "  [图片] 跳过：上传队列已满 (目标过慢?)",
    },

    # ----- image_uploader (tải ảnh AOI) -----
    "Chưa cấu hình thư mục ảnh nguồn/đích": {
        "en": "Image source/destination folder not configured",
        "zh": "未配置图片源/目标文件夹",
    },
    "Không tìm thấy ảnh mới trong %s": {
        "en": "No new image found in %s", "zh": "在 %s 中找不到新图片"},
    "Lỗi copy ảnh lên '%s': %s": {
        "en": "Error copying image to '%s': %s", "zh": "复制图片到 '%s' 出错：%s"},
    "Đã tải ảnh %s": {"en": "Image uploaded %s", "zh": "已上传图片 %s"},

    # ----- mes_api / data_reader (hiện trong log & banner lỗi) -----
    "máy chủ/proxy chặn request (HTTP %s). Kiểm tra URL MES và BỎ chọn 'Đi qua proxy hệ thống' trong Setting > API nếu MES là máy chủ nội bộ.": {
        "en": "server/proxy blocked the request (HTTP %s). Check the MES URL and UNCHECK 'Use system proxy' in Settings > API if MES is an internal server.",
        "zh": "服务器/代理拦截了请求 (HTTP %s)。请检查 MES 网址；若 MES 为内网服务器，请在 设置 > API 中取消勾选“经过系统代理”。",
    },
    "Chưa cài thư viện 'requests'": {
        "en": "The 'requests' library is not installed",
        "zh": "未安装 'requests' 库",
    },
    "MES từ chối kiểm tra SN (HTTP %d): %s": {
        "en": "MES rejected the SN check (HTTP %d): %s",
        "zh": "MES 拒绝了 SN 检查 (HTTP %d)：%s",
    },
    "SN không hợp lệ (MES không trả mã cho phép)": {
        "en": "Invalid SN (MES did not return an allow code)",
        "zh": "SN 无效 (MES 未返回允许码)",
    },
    "SN hợp lệ": {"en": "SN valid", "zh": "SN 有效"},
    "Lỗi GET kiểm tra SN: %s": {
        "en": "SN check GET error: %s", "zh": "SN 检查 GET 错误：%s"},
    "Chưa có dữ liệu cho ngày hôm nay (%s).\nThiếu thư mục: %s": {
        "en": "No data for today (%s).\nMissing folder: %s",
        "zh": "今天 (%s) 还没有数据。\n缺少文件夹：%s",
    },
    "Ngày hôm nay (%s) chưa có file '%s'.\nTrong thư mục: %s": {
        "en": "Today (%s) has no file '%s' yet.\nIn folder: %s",
        "zh": "今天 (%s) 还没有文件 '%s'。\n在文件夹：%s",
    },
    "Không tìm thấy file '%s' trong %s": {
        "en": "File '%s' not found in %s", "zh": "在 %s 中找不到文件 '%s'"},
    "File rỗng: %s": {"en": "Empty file: %s", "zh": "空文件：%s"},
    "File chưa có dòng dữ liệu: %s": {
        "en": "File has no data rows yet: %s", "zh": "文件还没有数据行：%s"},

    # ----- Hộp thoại Setting: tiêu đề tab -----
    "Chung": {"en": "General", "zh": "常规"},
    "PLC": {"en": "PLC", "zh": "PLC"},
    "API MES": {"en": "MES API", "zh": "MES API"},
    "Tải ảnh": {"en": "Image upload", "zh": "图片上传"},
    "Bên trái": {"en": "Left side", "zh": "左侧"},
    "Bên phải": {"en": "Right side", "zh": "右侧"},
    "Mã liệu": {"en": "Materials", "zh": "料号"},

    # ----- Setting: tab Chung -----
    "Ngôn ngữ:": {"en": "Language:", "zh": "语言："},
    "Chế độ:": {"en": "Mode:", "zh": "模式："},
    "Giả lập (không cần PLC / tay scan)": {
        "en": "Simulation (no PLC / scanner)", "zh": "模拟 (无需 PLC / 扫码枪)"},
    "PLC thật + nhập SN tay (không cần tay scan)": {
        "en": "Real PLC + manual SN (no scanner)",
        "zh": "真实 PLC + 手动输入 SN (无需扫码枪)",
    },
    "Thật (PLC + tay scan)": {
        "en": "Live (PLC + scanner)", "zh": "实机 (PLC + 扫码枪)"},
    "Chu kỳ đọc PLC:": {"en": "PLC poll interval:", "zh": "PLC 轮询周期："},
    "Chọn…": {"en": "Browse…", "zh": "选择…"},
    "Thư mục gốc dữ liệu:": {"en": "Data root folder:", "zh": "数据根目录："},
    "Thư mục con 4X:": {"en": "4X subfolder:", "zh": "4X 子目录："},
    "Thư mục con 8X:": {"en": "8X subfolder:", "zh": "8X 子目录："},
    "Thư mục con 16X:": {"en": "16X subfolder:", "zh": "16X 子目录："},
    "Mẫu tên file Trái:": {"en": "Left file name pattern:", "zh": "左侧文件名模式："},
    "Mẫu tên file Phải:": {"en": "Right file name pattern:", "zh": "右侧文件名模式："},
    "Đường dẫn = <gốc>/<con 4X|8X|16X>/<YYYYMMDD>/CCD1*|CCD2*": {
        "en": "Path = <root>/<4X|8X|16X sub>/<YYYYMMDD>/CCD1*|CCD2*",
        "zh": "路径 = <根>/<4X|8X|16X 子目录>/<YYYYMMDD>/CCD1*|CCD2*",
    },
    "Chỉ lấy dữ liệu của NGÀY HÔM NAY (báo lỗi nếu thiếu thư mục/file)": {
        "en": "Only use TODAY's data (error if folder/file is missing)",
        "zh": "仅读取“今天”的数据 (缺少文件夹/文件则报错)",
    },
    "Chọn thư mục gốc dữ liệu": {
        "en": "Choose data root folder", "zh": "选择数据根目录"},

    # ----- Setting: tab PLC -----
    "IP PLC chung:": {"en": "Shared PLC IP:", "zh": "公共 PLC IP："},
    "Port:": {"en": "Port:", "zh": "端口："},
    "Timeout:": {"en": "Timeout:", "zh": "超时："},
    "Mỗi bên có thể đặt IP/Port riêng trong tab Bên trái/phải.": {
        "en": "Each side may set its own IP/Port in the Left/Right tab.",
        "zh": "每一侧可在 左侧/右侧 标签页设置各自的 IP/端口。",
    },
    "Định dạng dữ liệu (Data Code):": {
        "en": "Data code:", "zh": "数据格式 (Data Code)："},
    "Binary/ASCII phải KHỚP cấu hình SLMP trên PLC.": {
        "en": "Binary/ASCII must MATCH the SLMP setting on the PLC.",
        "zh": "Binary/ASCII 必须与 PLC 上 SLMP 的设置一致。",
    },
    "Test kết nối PLC": {"en": "Test PLC connection", "zh": "测试 PLC 连接"},
    "vd D4206 (word) hoặc M100 (bit)": {
        "en": "e.g. D4206 (word) or M100 (bit)", "zh": "例如 D4206 (word) 或 M100 (bit)"},
    "Test đọc PLC": {"en": "Test read PLC", "zh": "测试读取 PLC"},
    "Đọc thử thanh ghi:": {"en": "Test-read register:", "zh": "试读寄存器："},
    "Test PLC": {"en": "Test PLC", "zh": "测试 PLC"},
    "Kết nối %s:%d OK.\nĐọc %s = %s": {
        "en": "Connected %s:%d OK.\nRead %s = %s",
        "zh": "连接 %s:%d 成功。\n读取 %s = %s",
    },
    "Lỗi đọc %s từ %s:%d:\n%s": {
        "en": "Error reading %s from %s:%d:\n%s",
        "zh": "读取 %s 出错 (从 %s:%d)：\n%s",
    },

    # ----- Setting: tab API -----
    "Kết nối chung (mọi loại đầu)": {
        "en": "Shared connection (all head types)", "zh": "公共连接 (所有探头类型)"},
    "Số lần retry:": {"en": "Retry count:", "zh": "重试次数："},
    "Kiểm tra chứng chỉ SSL": {"en": "Verify SSL certificate", "zh": "验证 SSL 证书"},
    "Mã nhân viên (empNo):": {
        "en": "Employee No. (empNo):", "zh": "员工编号 (empNo)："},
    "vd V3081479": {"en": "e.g. V3081479", "zh": "例如 V3081479"},
    "Đi qua proxy hệ thống": {"en": "Use system proxy", "zh": "经过系统代理"},
    "vd http://10.0.0.1:8080 (để trống = proxy hệ thống)": {
        "en": "e.g. http://10.0.0.1:8080 (empty = system proxy)",
        "zh": "例如 http://10.0.0.1:8080 (留空 = 系统代理)",
    },
    "Proxy thủ công:": {"en": "Manual proxy:", "zh": "手动代理："},
    "MES nội bộ: BỎ chọn proxy. Chỉ tích nếu MES nằm ngoài mạng và phải qua proxy công ty.": {
        "en": "Internal MES: UNCHECK proxy. Only tick it if MES is outside the network and must go through the company proxy.",
        "zh": "内网 MES：取消勾选代理。仅当 MES 在外网且必须经过公司代理时才勾选。",
    },
    "API đầu %s — chọn đầu %s sẽ chạy theo API này": {
        "en": "%s head API — selecting the %s head runs through this API",
        "zh": "%s 探头 API — 选择 %s 探头时将使用此 API 运行",
    },
    "URL POST (upload):": {"en": "POST URL (upload):", "zh": "POST 网址 (上传)："},
    "POST OK khi body chứa:": {
        "en": "POST OK when body contains:", "zh": "当响应体包含以下内容时 POST 成功："},
    "Tên trạm (stationName):": {
        "en": "Station name (stationName):", "zh": "工站名称 (stationName)："},
    "vd STATION-4X (mỗi loại đầu 1 tên khác nhau)": {
        "en": "e.g. STATION-4X (a different name per head type)",
        "zh": "例如 STATION-4X (每种探头类型一个不同名称)",
    },
    "POST body: sn + stationName (theo loại đầu) + empNo + timer (L1: v1 - v2 - ...; L2: ...).": {
        "en": "POST body: sn + stationName (per head type) + empNo + timer (L1: v1 - v2 - ...; L2: ...).",
        "zh": "POST 请求体：sn + stationName (按探头类型) + empNo + timer (L1: v1 - v2 - ...; L2: ...)。",
    },
    "Bật kiểm tra SN bằng GET": {
        "en": "Enable SN check via GET", "zh": "启用通过 GET 检查 SN"},
    "URL GET (tiền tố):": {"en": "GET URL (prefix):", "zh": "GET 网址 (前缀)："},
    "URL GET (hậu tố):": {"en": "GET URL (suffix):", "zh": "GET 网址 (后缀)："},
    "SN hợp lệ khi body bằng:": {
        "en": "SN valid when body equals:", "zh": "当响应体等于以下内容时 SN 有效："},
    "vd 200 (để trống = chỉ cần HTTP 2xx)": {
        "en": "e.g. 200 (empty = HTTP 2xx is enough)",
        "zh": "例如 200 (留空 = 只要 HTTP 2xx)",
    },
    "vd http://mes/api/check?sn=": {
        "en": "e.g. http://mes/api/check?sn=", "zh": "例如 http://mes/api/check?sn="},
    "vd &station=OP10 (có thể để trống)": {
        "en": "e.g. &station=OP10 (may be empty)", "zh": "例如 &station=OP10 (可留空)"},
    "vd 0 — body BẰNG ĐÚNG giá trị này thì SN hợp lệ": {
        "en": "e.g. 0 — SN is valid only if body equals this value exactly",
        "zh": "例如 0 — 响应体完全等于此值时 SN 才有效",
    },
    "Mỗi loại đầu có endpoint riêng. POST = tải kết quả; GET kiểm tra SN tới <tiền tố>+SN+<hậu tố> (SN sai -> CHẶN, không tải lên).": {
        "en": "Each head type has its own endpoint. POST = upload results; GET checks SN at <prefix>+SN+<suffix> (bad SN -> BLOCK, no upload).",
        "zh": "每种探头类型都有各自的端点。POST = 上传结果；GET 检查 SN 到 <前缀>+SN+<后缀> (SN 错误 -> 拦截，不上传)。",
    },

    # ----- Setting: tab Tải ảnh -----
    "Bật tải ảnh AOI lên link đích": {
        "en": "Upload AOI images to destination link",
        "zh": "上传 AOI 图片到目标链接",
    },
    "Cấu trúc thư mục ảnh (mọi loại đầu)": {
        "en": "Image folder structure (all head types)",
        "zh": "图片文件夹结构 (所有探头类型)",
    },
    "Thư mục con ảnh:": {"en": "Image subfolder:", "zh": "图片子目录："},
    "Thư mục ảnh OK:": {"en": "OK image folder:", "zh": "OK 图片文件夹："},
    "Thư mục ảnh NG:": {"en": "NG image folder:", "zh": "NG 图片文件夹："},
    "Phần mở rộng ảnh:": {"en": "Image extensions:", "zh": "图片扩展名："},
    "Nguồn = <thư mục đầu>/<con ảnh>/<YYYY-MM-DD>/<OK|NG>; đích = <link>/<YYYYMMDD>/.": {
        "en": "Source = <head folder>/<image sub>/<YYYY-MM-DD>/<OK|NG>; destination = <link>/<YYYYMMDD>/.",
        "zh": "源 = <探头文件夹>/<图片子目录>/<YYYY-MM-DD>/<OK|NG>；目标 = <链接>/<YYYYMMDD>/。",
    },
    "Ảnh đầu %s": {"en": "%s head image", "zh": "%s 探头图片"},
    "Đổi tên khi tải: <SN>_<YYYYMMDD HHMMSS>_Passed|Failed.<ext> (vd 123456_20260609 183415_Passed.jpg).": {
        "en": "Rename on upload: <SN>_<YYYYMMDD HHMMSS>_Passed|Failed.<ext> (e.g. 123456_20260609 183415_Passed.jpg).",
        "zh": "上传时重命名：<SN>_<YYYYMMDD HHMMSS>_Passed|Failed.<ext> (例如 123456_20260609 183415_Passed.jpg)。",
    },
    "Thư mục ảnh nguồn:": {"en": "Source image folder:", "zh": "源图片文件夹："},
    "Link tải lên (đích):": {"en": "Upload link (destination):", "zh": "上传链接 (目标)："},
    "vd D:/AOI/8X (chứa thư mục con Image)": {
        "en": "e.g. D:/AOI/8X (contains the Image subfolder)",
        "zh": "例如 D:/AOI/8X (包含 Image 子目录)",
    },
    "vd //10.222.48.222/AOI/17G": {
        "en": "e.g. //10.222.48.222/AOI/17G", "zh": "例如 //10.222.48.222/AOI/17G"},
    "Chọn thư mục": {"en": "Choose folder", "zh": "选择文件夹"},

    # ----- Setting: tab Bên trái / phải -----
    "Cổng COM tay scan:": {"en": "Scanner COM port:", "zh": "扫码枪 COM 口："},
    "Baudrate:": {"en": "Baud rate:", "zh": "波特率："},
    "Tiền tố file (CCD):": {"en": "File prefix (CCD):", "zh": "文件前缀 (CCD)："},
    "Trigger 4X:": {"en": "4X trigger:", "zh": "4X 触发："},
    "Done 4X:": {"en": "4X done:", "zh": "4X 完成："},
    "Trigger 8X:": {"en": "8X trigger:", "zh": "8X 触发："},
    "Done 8X:": {"en": "8X done:", "zh": "8X 完成："},
    "Trigger 16X:": {"en": "16X trigger:", "zh": "16X 触发："},
    "Done 16X:": {"en": "16X done:", "zh": "16X 完成："},
    "Trigger/Done nhận BIT (M…) hoặc thanh ghi WORD (D…); word coi giá trị ≠ 0 là 'bật'.": {
        "en": "Trigger/Done accept a BIT (M…) or a WORD register (D…); for a word, value ≠ 0 means 'on'.",
        "zh": "Trigger/Done 可填 BIT (M…) 或 WORD 寄存器 (D…)；word 时值 ≠ 0 视为“开”。",
    },
    "Thanh ghi kết quả SN (1=OK/2=NG):": {
        "en": "SN result register (1=OK/2=NG):", "zh": "SN 结果寄存器 (1=OK/2=NG)："},
    "vd D100 — ghi 1=OK / 2=NG (để trống = không ghi)": {
        "en": "e.g. D100 — write 1=OK / 2=NG (empty = no write)",
        "zh": "例如 D100 — 写入 1=OK / 2=NG (留空 = 不写)",
    },
    "  Ghi kết quả SN về PLC %s = %d": {
        "en": "  Wrote SN result to PLC %s = %d",
        "zh": "  已写入 SN 结果到 PLC %s = %d",
    },
    "PLC IP riêng (trống = chung):": {
        "en": "Dedicated PLC IP (empty = shared):", "zh": "独立 PLC IP (留空 = 公共)："},
    "PLC Port riêng (0 = chung):": {
        "en": "Dedicated PLC Port (0 = shared):", "zh": "独立 PLC 端口 (0 = 公共)："},

    # ----- Setting: tab Mã liệu -----
    "Chuyên án": {"en": "Project", "zh": "专案"},
    "Tên mã liệu": {"en": "Material name", "zh": "料号名称"},
    "Số đầu 4X": {"en": "4X heads", "zh": "4X 探头数"},
    "Số đầu 8X": {"en": "8X heads", "zh": "8X 探头数"},
    "Số đầu 16X": {"en": "16X heads", "zh": "16X 探头数"},
    "Thêm mã liệu": {"en": "Add material", "zh": "添加料号"},
    "Nhập từ Excel…": {"en": "Import from Excel…", "zh": "从 Excel 导入…"},
    "Xóa dòng chọn": {"en": "Delete selected row", "zh": "删除所选行"},
    "Cột: Chuyên án | Tên mã liệu | Số đầu 4X / 8X / 16X (loại nào không có để trống = 0). Mỗi chuyên án gom nhiều mã liệu; ngoài giao diện chọn Chuyên án rồi mới chọn Mã liệu, và chỉ hiện đúng các loại đầu mà mã liệu có. Nhập từ Excel: trùng (chuyên án + tên) sẽ cập nhật, còn lại thêm mới.": {
        "en": "Columns: Project | Material name | 4X / 8X / 16X heads (leave blank = 0 if absent). Each project groups several materials; the UI selects Project then Material, and shows only the head types the material actually has. Import from Excel: duplicates (project + name) are updated, the rest are added.",
        "zh": "列：专案 | 料号名称 | 4X / 8X / 16X 探头数 (没有的留空 = 0)。每个专案归集多个料号；界面先选专案再选料号，且只显示该料号实际拥有的探头类型。从 Excel 导入：重复 (专案 + 名称) 将被更新，其余新增。",
    },
    "Chọn file mã liệu (Excel/CSV)": {
        "en": "Choose material file (Excel/CSV)", "zh": "选择料号文件 (Excel/CSV)"},
    "Excel/CSV (*.xlsx *.xls *.xlsm *.csv);;Tất cả file (*)": {
        "en": "Excel/CSV (*.xlsx *.xls *.xlsm *.csv);;All files (*)",
        "zh": "Excel/CSV (*.xlsx *.xls *.xlsm *.csv);;所有文件 (*)",
    },
    "Nhập mã liệu": {"en": "Import materials", "zh": "导入料号"},
    "Không đọc được file:\n%s": {
        "en": "Could not read the file:\n%s", "zh": "无法读取文件：\n%s"},
    "Không tìm thấy mã liệu hợp lệ trong file.\nCần cột Tên mã liệu + ít nhất 1 cột Số đầu 4X / 8X / 16X.": {
        "en": "No valid materials found in the file.\nA Material name column + at least one of 4X / 8X / 16X heads is required.",
        "zh": "文件中未找到有效料号。\n需要“料号名称”列 + 至少一个 4X / 8X / 16X 探头数列。",
    },
    "Đã nhập từ:\n%s\n\nThêm mới: %d — Cập nhật: %d": {
        "en": "Imported from:\n%s\n\nAdded: %d — Updated: %d",
        "zh": "已从以下导入：\n%s\n\n新增：%d — 更新：%d",
    },
    "\nBỏ qua %d dòng không có tên mã.": {
        "en": "\nSkipped %d rows without a material name.",
        "zh": "\n已跳过 %d 行没有料号名称的数据。",
    },
}


# ---------------------------------------------------------------------- #
#  API                                                                    #
# ---------------------------------------------------------------------- #
def available_languages():
    """Danh sách [(mã, nhãn)] để dựng combo chọn ngôn ngữ."""
    return list(LANGUAGES)


def current_language():
    return _state["lang"]


def normalize(code):
    """Trả về mã hợp lệ; mã lạ -> ngôn ngữ mặc định."""
    return code if code in _LANG_CODES else DEFAULT_LANGUAGE


def set_language(code):
    """Đổi ngôn ngữ hiện tại và gọi lại mọi listener (để retranslate)."""
    code = normalize(code)
    _state["lang"] = code
    for cb in list(_listeners):
        try:
            cb()
        except Exception:            # noqa: BLE001  (1 listener lỗi không chặn các listener khác)
            pass
    return code


def tr(text):
    """Dịch 'text' (chuỗi nguồn tiếng Việt) sang ngôn ngữ hiện tại."""
    lang = _state["lang"]
    if lang == DEFAULT_LANGUAGE or not text:
        return text
    entry = _TR.get(text)
    if not entry:
        return text
    return entry.get(lang, text)


def add_listener(callback):
    """Đăng ký hàm gọi lại khi đổi ngôn ngữ (vd window.retranslate)."""
    if callback not in _listeners:
        _listeners.append(callback)


def remove_listener(callback):
    if callback in _listeners:
        _listeners.remove(callback)
