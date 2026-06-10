# MES Uploader — Tải nội dung đo lên hệ thống MES

Phần mềm desktop (PySide6) đọc kết quả đo từ file (CSV/Excel) và tải lên hệ
thống **MES** qua API. Giao diện gồm **2 bên Trái / Phải** hoạt động **độc
lập** nhưng cùng **một lưu trình**, mỗi bên có 1 tay scan (cổng COM) riêng và
nhận tín hiệu chạy từ **PLC Mitsubishi** (MC Protocol 3E / SLMP).

---

## 1. Lưu trình mỗi bên

```
Chọn chuyên án + mã liệu + loại đầu (4X/8X/16X)  ->  Bấm "Bắt đầu"
        │
        ▼
Quét SN bằng tay scan của bên đó  (Trái = CCD1, Phải = CCD2)
        │
        ▼
Lặp N lần  (N = số đầu của loại đã chọn theo mã liệu):
   • PLC bật bit trigger (0 -> 1)  → app đọc DÒNG MỚI NHẤT trong file
   • theo kết quả OK/NG → lấy ẢNH MỚI NHẤT (OK/NG) và tải lên link đích (nền)
   • app ghi bit "done" = 1 → RESET bit trigger đã nhận về 0 → hạ done
        │
        ▼
Đủ N đầu  ->  GỘP dữ liệu  ->  POST 1 lần lên MES
   JSON: { "sn": "...", "stationName": "...", "empNo": "...", "timer": "dataNN_LM:..." }
        │
        ▼
Hiện kết quả  ->  quay lại chờ quét SN tiếp theo
```

Ví dụ: mã liệu **ABC** có *2 đầu 8X* và *1 đầu 16X*. Chọn ABC + 8X → chạy 2
lần (2 tín hiệu PLC) rồi tải 1 lần. Mã **BCD** có *4 đầu 8X* → chạy 4 lần.

---

## 2. Cài đặt & chạy

```bash
pip install -r requirements.txt
python run.py
```

- Lần đầu chạy sẽ tự tạo `config.json` (mặc định **bật chế độ giả lập** + 2 mã
  liệu mẫu ABC/BCD + trỏ vào `sample_data/`), giúp thử ngay **không cần phần
  cứng**.
- Sửa cấu hình bằng nút **⚙ Setting** trên giao diện (lưu vào `config.json`).
- Xem `config.example.json` để biết toàn bộ tham số.

> **Đổi ngôn ngữ:** vào **⚙ Setting > Chung > Ngôn ngữ** chọn **Tiếng Việt /
> 中文 / English**. Toàn bộ giao diện (cửa sổ chính, 2 panel, hộp thoại Setting,
> nhật ký/trạng thái) đổi **ngay lập tức** sang ngôn ngữ đã chọn; lựa chọn được
> lưu vào `config.json` (trường `"language"`) nên lần mở sau giữ nguyên. Bấm
> **Hủy** trong hộp thoại sẽ hoàn nguyên về ngôn ngữ trước đó.

### Thử nhanh ở chế độ giả lập
1. Bấm **Bắt đầu** ở 1 bên.
2. Gõ SN vào ô *"Nhập SN giả lập"* → bấm **Quét (giả lập)**.
3. Bấm **Tín hiệu PLC (giả lập)** đúng *số đầu* lần (vd ABC+8X = 2 lần).
4. App đọc dòng mới nhất mỗi lần, gộp lại và POST (xem log).

### Đóng gói thành 1 file `.exe` (Windows)

> **Bản `.exe` phải build TRÊN WINDOWS** — PyInstaller không build chéo
> (chạy trên Linux/macOS chỉ ra file cho chính hệ đó, không ra `.exe` Windows).
> Máy build cần **Python 3.9+** (khi cài nhớ tích *Add Python to PATH*).

1. Vào thư mục `mes_uploader_app`, **bấm đúp `build_exe.bat`** (hoặc trong `cmd`
   gõ `build_exe.bat`).
2. Script tự: cài `requirements-build.txt` (PySide6, pyserial, requests,
   openpyxl, PyInstaller) → đóng gói **1 file** → chép `sample_data/` +
   `config.example.json` ra cạnh exe.
3. Kết quả: **`dist\MES_Uploader.exe`**. Copy cả thư mục `dist` sang máy chạy.

- Lần đầu chạy exe sẽ tự tạo **`config.json` ngay CẠNH exe** (giữ nguyên các
  lần sau, sửa được). Vào **⚙ Setting** để trỏ đường dẫn dữ liệu / PLC / API
  thật của nhà máy.
- App là GUI nên đóng gói ở chế độ **không hiện cửa sổ console** (`--windowed`).
- **Icon**: `assets/ninja.ico` (icon file `.exe`) + `assets/ninja.png` (icon cửa
  sổ/thanh tác vụ). Muốn ĐỔI icon: thay 2 file này (giữ tên), hoặc sửa rồi chạy
  `python assets/make_icon.py` để sinh lại từ ảnh nguồn.
- Test cấu hình đóng gói trên Linux/macOS: `./build_exe.sh` (ra file chạy cho
  hệ đó để kiểm thử, **không** phải `.exe` Windows).

---

## 3. Cấu trúc file dữ liệu

```
<base_dir>/<sub_8x>/<YYYYMMDD>/CCD1*   ← bên trái  (8X)
<base_dir>/<sub_8x>/<YYYYMMDD>/CCD2*   ← bên phải  (8X)
<base_dir>/<sub_16x>/<YYYYMMDD>/CCD1*  ← bên trái  (16X)
<base_dir>/<sub_16x>/<YYYYMMDD>/CCD2*  ← bên phải  (16X)
```

Mỗi file có cột: `Time, Judge, IspTime, Data01 … DataNN`
- **Judge** = kết quả OK/NG (phần "jugle").
- **Data01..N** = các giá trị đo (số cột tự nhận, không cố định).
- "Lấy nội dung mới nhất" = **dòng cuối cùng** của file mới nhất trong thư mục
  ngày hôm nay.

> Phần mềm **tự nhận diện** CSV hay Excel theo *nội dung file* (không dựa vào
> đuôi). Trong dữ liệu mẫu có file `.csv` thực chất là `.xlsx` — vẫn đọc đúng.

### Dữ liệu cập nhật theo ngày — báo lỗi khi thiếu

File được xuất theo thư mục ngày `YYYYMMDD`. Mặc định **`require_today = true`**:
phần mềm **chỉ đọc dữ liệu của NGÀY HÔM NAY**. Nếu khi nhận tín hiệu chạy mà:

- **thiếu thư mục ngày hôm nay**, hoặc
- thư mục ngày hôm nay **chưa có file** CCD1*/CCD2*, hoặc
- file **chưa có dòng dữ liệu** nào,

thì phần mềm **BÁO LỖI rõ ràng** (banner đỏ "LỖI DỮ LIỆU" + 1 dòng LỖI trong
bảng + ghi nhật ký kèm đường dẫn còn thiếu), **HỦY SN đang chạy và KHÔNG tải
lên MES** — tránh lấy nhầm dữ liệu của ngày cũ. Vẫn nhả handshake để PLC không
bị treo; thao tác viên xử lý rồi quét lại.

> Bỏ chọn *"Chỉ lấy dữ liệu của ngày hôm nay"* trong **Setting > Chung**
> (`require_today = false`) nếu muốn cho phép lấy dữ liệu ở thư mục ngày mới
> nhất hiện có (kể cả ngày cũ).

---

## 4. Cấu hình PLC (handshake bằng bit)

Theo từng bên, mỗi loại đầu có 2 địa chỉ bit (đặt trong Setting > Bên trái/phải):

| Tham số | Ý nghĩa | Mặc định Trái | Mặc định Phải |
|--------|---------|--------------|--------------|
| `trig_8x`  | PLC bật =1 báo "chạy" đầu 8X (app đọc)   | M100 | M200 |
| `done_8x`  | app ghi =1 báo "hoàn thành" 8X về PLC    | M101 | M201 |
| `trig_16x` | PLC bật =1 báo "chạy" đầu 16X            | M110 | M210 |
| `done_16x` | app ghi =1 báo "hoàn thành" 16X về PLC   | M111 | M211 |
| `sn_result_reg` | app ghi **kết quả kiểm tra SN**: `1`=OK, `2`=NG (thanh ghi word, vd `D100`/`D200`; trống = không ghi) | D100 | D200 |

- **Địa chỉ trigger/done nhận BIT hoặc WORD**: bit `M…` (đọc/ghi 0/1) **hoặc**
  thanh ghi dữ liệu `D…` (word). Với word, app coi **giá trị ≠ 0 = "chạy"**, ghi
  done = 1 và reset trigger = 0. App tự nhận loại theo tiền tố (`M/X/Y…`=bit,
  `D/W/R`=word) — Mitsubishi dùng `D` cho thanh ghi dữ liệu (không có "DM").
- 1 PLC dùng chung 2 bên (IP/Port ở tab **PLC**). Nếu dùng **2 PLC riêng**, đặt
  `plc_ip` / `plc_port` trong tab từng bên.
- Bắt tay: app phát hiện **sườn lên** của bit trigger → đọc dữ liệu → ghi
  `done=1` → **RESET bit trigger đã nhận về 0** → hạ `done=0` → sẵn sàng cho đầu
  tiếp theo. (App tự ghi trigger về 0 sau khi nhận — PLC pulse trigger rồi chờ
  app reset.)
- **Kiểm tra SN (GET)** xong, app ghi kết quả về `sn_result_reg`: **OK→1, NG→2**
  (xem mục API). Để PLC biết SN có hợp lệ để chạy hay không.

---

## 5. API MES

> **Mỗi loại đầu (4X / 8X / 16X) có API riêng.** Chọn loại đầu nào thì cả
> bước kiểm tra SN (GET) lẫn upload (POST) đều chạy theo **endpoint của loại
> đầu đó** (`Setting > API MES > "API đầu 4X/8X/16X"`). Mỗi loại đầu cũng có
> **`stationName` riêng**. Các tham số kết nối (timeout, retry, SSL, proxy) và
> **`empNo`** (mã nhân viên) **dùng chung** cho mọi loại đầu.

### 5.1. Kiểm tra SN bằng GET (trước khi chạy)

Ngay sau khi quét SN (trước khi nhận tín hiệu PLC), app gọi **GET** để hỏi MES
xem SN có được phép chạy không:

```
GET  <check_url_prefix> + SN + <check_url_suffix>
SN hợp lệ  ⇔  nội dung trả về BẰNG ĐÚNG `check_ok_value` (mặc định "0")
```

> Giống `main.py`: `req = requests.get(sn_link1 + SN + sn_link2)` rồi
> `if req.text == '0'`. So khớp **bằng đúng** (không phải "chứa") để tránh nhận
> nhầm phản hồi lỗi có lẫn ký tự `0` (mã lỗi, số đếm…). Để trống
> `check_ok_value` → chỉ cần HTTP 2xx.

- **Hợp lệ** → cho chạy bình thường.
- **Không hợp lệ / GET lỗi mạng / HTTP ≠ 2xx** → **CHẶN**: hiện "SN BỊ CHẶN"
  (banner hổ phách + dòng CHẶN trong bảng kèm lý do từ MES), **không chạy, không
  tải lên**, chờ **quét mã khác**.
- Tắt kiểm tra: bỏ chọn *"Bật kiểm tra SN bằng GET"* trong Setting > API
  (`check_enabled=false`).

### 5.2. Upload bằng POST (sau khi xong tất cả đầu)

`requests.post(url, json=payload)` — 1 SN gọi **1 lần** sau khi xong tất cả đầu.

```json
{
  "sn": "SN123",
  "stationName": "STATION-8X",
  "empNo": "V3081479",
  "timer": "data01_L1:26.321; …; data146_L1:2.48; data01_L2:22.8; …; data146_L2:10.1"
}
```

- `sn` = mã quét từ tay scan.
- `stationName` = tên trạm theo **loại đầu** đang chạy (4X / 8X / 16X mỗi loại
  một tên — đặt trong `Setting > API MES > "API đầu …" > Tên trạm`).
- `empNo` = mã nhân viên (dùng chung, đặt ở `Setting > API MES > Mã nhân viên`).
- `timer` = **toàn bộ giá trị đo** của các đầu ghép thành 1 chuỗi, mỗi phần tử
  `dataNN_LM:giá_trị` cách nhau `"; "`:
  - `M` = thứ tự lần đọc (đầu), bắt đầu từ 1 → `L1`, `L2`, …
  - `NN` = thứ tự giá trị đo, bắt đầu từ 1, tối thiểu 2 chữ số (`01`, `02`, … `146`).
  - Ví dụ 2 đầu 8X: `data01_L1:…; …; data146_L1:…; data01_L2:…; …; data146_L2:…`.
- **POST thành công** ⇔ HTTP 2xx **và** body CHỨA `post_ok_contains` (mặc định
  "200"). Để trống `post_ok_contains` → chỉ cần HTTP 2xx. Body không khớp →
  báo "gửi lỗi" (banner hổ phách, cột MES `✗`).
- Có retry (lùi dần 2/4/8s) khi lỗi mạng.

> **Lưu trình không đổi:** quét SN → kiểm tra GET → (nhận tín hiệu PLC × số đầu)
> → POST. Trong suốt quá trình này **mọi mã quét mới đều bị bỏ qua**; chỉ sau khi
> POST xong (hoặc SN bị chặn/lỗi) mới nhận mã tiếp theo.

---

## 6. Tải ảnh AOI lên link mạng

> Cấu hình ở **⚙ Setting > Tải ảnh**. Sau **mỗi đầu** (mỗi tín hiệu PLC), ngoài
> đọc dữ liệu, app còn lấy **ảnh mới nhất** theo kết quả OK/NG và **copy** lên
> link đích. **Mỗi loại đầu (4X / 8X / 16X) có thư mục nguồn + link đích riêng.**

**Nguồn (ở máy)** — theo từng loại đầu:

```
<source_dir>/<Image>/<YYYY-MM-DD>/OK/   ← ảnh khi kết quả OK   (vd 2026-06-09)
<source_dir>/<Image>/<YYYY-MM-DD>/NG/   ← ảnh khi kết quả NG
```

**Đích (link mạng)** — tạo thư mục theo ngày rồi copy ảnh vào:

```
<upload_dir>/<YYYYMMDD>/    (vd //10.222.48.222/AOI/17G/20260609/)
```

- Nhận **OK** → vào thư mục `OK`, nhận **NG** → vào thư mục `NG`, lấy **ảnh mới
  nhất** (theo thời gian sửa đổi).
- **Đổi tên** khi tải lên: `<SN>_<YYYYMMDD HHMMSS>_<Passed|Failed>.<ext>`
  (Passed = OK, Failed = NG). Ví dụ: `123456_20260609 183415_Passed.jpg`.
- **"Tải lên" = copy file** sang đường dẫn chia sẻ mạng (UNC, vd
  `//10.222.48.222/AOI/17G`). Việc copy chạy ở **luồng nền** nên **không làm
  chậm dây chuyền**; thành công/lỗi đều ghi vào **NHẬT KÝ** (dòng `[ẢNH]`).
- Tham số chung: tên thư mục con ảnh (`Image`), tên thư mục `OK`/`NG`, danh sách
  phần mở rộng ảnh; áp dụng cho mọi loại đầu.
- Thư mục ngày nguồn theo cờ **"Chỉ lấy dữ liệu của ngày hôm nay"** (mục
  *Setting > Chung*): bật → chỉ lấy ảnh **hôm nay**; tắt → lùi về **ngày mới
  nhất** có ảnh.
- Tắt toàn bộ: bỏ chọn *"Bật tải ảnh AOI lên link đích"*. Loại đầu nào **chưa
  điền** thư mục nguồn/đích sẽ **bỏ qua im lặng**.

---

## 7. Cấu trúc mã nguồn

```
run.py                         điểm chạy (PySide6)
config.example.json            mẫu cấu hình
mes_uploader/
  config.py                    nạp/lưu cấu hình JSON, mã liệu, địa chỉ bit
  i18n.py                      đa ngôn ngữ Việt/Trung/Anh (gettext, đổi nóng)
  material_import.py           nhập danh sách mã liệu từ file Excel/CSV
  data_reader.py               tìm file mới nhất + đọc dòng mới nhất (CSV/XLSX)
  mes_api.py                   dựng payload + POST (retry)
  image_uploader.py            lấy ảnh OK/NG mới nhất + đổi tên + copy lên link
  hardware/
    mitsubishi_plc.py          MC Protocol 3E (module gốc của bạn)
    plc_client.py              wrapper kết nối + MockPlcClient (giả lập)
    scanner.py                 đọc tay scan qua COM (pyserial)
  core/
    side_worker.py             máy trạng thái lưu trình 1 bên (độc lập Qt)
  ui/
    main_window.py             cửa sổ chính (2 panel + Setting)
    side_panel.py              panel 1 bên
    settings_dialog.py         hộp thoại Setting + quản lý mã liệu
tests/                         kiểm thử headless (không cần phần cứng)
sample_data/                   dữ liệu mẫu để chạy thử
```

Chạy test (không cần phần cứng / Qt):
```bash
python -m tests.test_data_reader          # đọc CSV/XLSX + dựng payload
python -m tests.test_worker               # lưu trình 1 bên (gộp đầu, POST)
python -m tests.test_date_required        # đọc theo ngày + báo lỗi khi thiếu
python -m tests.test_worker_missing_today # thiếu dữ liệu hôm nay -> hủy, không POST
python -m tests.test_api_check            # GET kiểm tra SN + POST theo body
python -m tests.test_worker_check_sn      # SN bị chặn -> chờ quét lại; SN tốt -> POST
python -m tests.test_material_import      # nhập mã liệu từ Excel/CSV
python -m tests.test_config_api           # API riêng theo loại đầu + migrate cấu hình cũ
python -m tests.test_i18n                 # đa ngôn ngữ Việt/Trung/Anh + lưu 'language'
python -m tests.test_image_uploader       # tải ảnh AOI: lấy ảnh mới nhất + đổi tên + copy
```

---

## 8. Quản lý mã liệu (kèm nhập từ Excel)

Vào **⚙ Setting > Mã liệu**. Mỗi mã liệu thuộc một **Chuyên án** và gồm:
**Tên mã liệu**, **Số đầu 4X / 8X / 16X** (số đầu = số lần nhận tín hiệu PLC
trước khi gộp & POST). Ngoài giao diện chọn **Chuyên án → Mã liệu → Loại đầu**;
mỗi chuyên án có danh sách mã liệu riêng và chỉ hiện đúng các loại đầu mà mã
liệu thực sự có.

- **Thêm mã liệu / Xóa dòng chọn**: thêm/sửa/xóa trực tiếp trong bảng.
- **Nhập từ Excel…**: chọn 1 file `.xlsx`/`.xls`/`.csv` để nạp **hàng loạt**:
  - Cột: `Chuyên án | Tên mã liệu | Số đầu 4X | Số đầu 8X | Số đầu 16X`. Cột
    **Chuyên án** và **Số đầu 4X** là **tùy chọn** (thiếu Chuyên án = nhóm
    chung; thiếu cột số đầu nào = 0 đầu loại đó).
  - **Tự nhận dòng tiêu đề** (kể cả tiếng Việt có dấu, không phân biệt thứ tự
    cột); nếu file **không có tiêu đề** thì đọc theo thứ tự cột cũ (1 = tên,
    2 = số đầu 8X, 3 = số đầu 16X). Muốn nhập **Chuyên án** hoặc **Số đầu 4X**
    thì file cần có dòng tiêu đề.
  - Tự nhận diện CSV hay Excel **theo nội dung** (dùng chung bộ đọc với dữ
    liệu đo). Dòng trống và dòng **không có tên mã** sẽ bị bỏ qua.
  - **Gộp theo (chuyên án + tên)**: mã trùng sẽ được **cập nhật** số đầu, mã
    mới sẽ **thêm** vào bảng. Sau khi nhập xong, bấm **OK** để lưu vào
    `config.json`.
- File mẫu: `sample_data/mau_ma_lieu.xlsx` (5 cột như trên, gom theo chuyên án).

> Lưu ý: nút *Nhập từ Excel* chỉ đổ dữ liệu vào bảng — phải bấm **OK** ở hộp
> thoại Setting thì cấu hình mới được ghi xuống `config.json`.

---

## 9. Giả định hiện tại (báo nếu cần đổi)

1. **1 PLC dùng chung** 2 bên (vẫn hỗ trợ 2 PLC qua IP/Port riêng mỗi bên).
2. Chọn **Chuyên án → Mã liệu → Loại đầu** trên panel; chỉ hiện loại đầu
   (4X/8X/16X) mà mã liệu có; số lần chạy lấy theo mã liệu.
3. Quét SN **trước**, rồi mới tới các tín hiệu chạy của PLC.
4. Kết quả OK/NG = tổng hợp Judge (NG nếu có bất kỳ đầu NG) — chỉ dùng để
   **hiển thị** trên giao diện; body POST mới (`sn/stationName/empNo/timer`)
   không gửi trường này.
5. Tay trái → panel trái (CCD1), tay phải → panel phải (CCD2).
6. **Tải ảnh = copy file** lên thư mục chia sẻ mạng (UNC). Thư mục nguồn/đích
   đặt **theo loại đầu** (4X/8X/16X), **dùng chung cho cả 2 bên** — nếu mỗi bên
   cần thư mục ảnh riêng thì báo để tách thêm chiều Trái/Phải.
