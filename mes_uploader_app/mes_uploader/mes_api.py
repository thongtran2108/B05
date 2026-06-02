# -*- coding: utf-8 -*-
"""Dựng JSON và POST nội dung lên hệ thống MES.

Theo yêu cầu:
  - 1 SN gọi API 1 lần, GỘP dữ liệu của tất cả các đầu.
  - Trường "data" chỉ chứa các giá trị đo Data01..N (data_format mặc định
    = "values_only"). Vẫn hỗ trợ thêm "full_row" / "structured" để chỉnh
    nhanh trong Setting nếu MES cần định dạng khác.
  - JSON: {"sn", "project", "material", "measuring_head",
           "result": "OK"/"NG", "data": ...}
    (project = chuyên án, material = mã liệu, measuring_head = loại đầu đo)
"""

import time

from .i18n import tr

try:
    import requests
except ImportError:                      # cho phép import module khi chưa cài requests
    requests = None


# ---------------------------------------------------------------------- #
#  Kết quả tổng: OK nếu MỌI đầu đều OK, ngược lại NG                      #
# ---------------------------------------------------------------------- #
def overall_result(readings):
    if not readings:
        return "NG"
    return "OK" if all(str(r.get("judge", "")).upper() == "OK"
                       for r in readings) else "NG"


# ---------------------------------------------------------------------- #
#  Dựng payload JSON                                                      #
# ---------------------------------------------------------------------- #
def build_payload(sn, readings, data_format="values_only",
                  project="", material="", measuring_head=""):
    """readings: list dict trả về từ data_reader.read_latest_measurement,
    theo đúng thứ tự các lần chạy (đầu 1, đầu 2, ...).

    project        : chuyên án đang chạy
    material       : mã liệu đang chạy
    measuring_head : loại đầu đo đang chạy ("4X" / "8X" / "16X")

    - values_only : data = [[Data01..N của đầu 1], [... đầu 2], ...]
    - full_row    : data = ["Time,Judge,...,DataN" (đầu 1), ...]
    - structured  : data = [{"Data01": .., ...}, ...]
    Nếu chỉ có 1 đầu thì data vẫn là list 1 phần tử (đồng nhất, dễ parse).
    """
    if data_format == "full_row":
        data = [",".join("" if c is None else str(c) for c in r["raw"])
                for r in readings]
    elif data_format == "structured":
        data = [dict(zip(r["headers"], r["values"])) for r in readings]
    else:  # values_only (mặc định)
        data = [r["values"] for r in readings]

    return {
        "sn": sn,
        "project": project,
        "material": material,
        "measuring_head": measuring_head,
        "result": overall_result(readings),
        "data": data,
    }


# ---------------------------------------------------------------------- #
#  Gửi POST (có retry khi lỗi mạng)                                       #
# ---------------------------------------------------------------------- #
def short_error(code, text):
    """Rút gọn nội dung lỗi để hiện trong nhật ký (tránh đổ cả trang HTML)."""
    t = (text or "").strip()
    low = t.lower()
    if ("<html" in low or "<!doctype" in low or "squid" in low
            or "err_access_denied" in low or "proxy" in low):
        return (tr("máy chủ/proxy chặn request (HTTP %s). Kiểm tra URL MES và "
                   "BỎ chọn 'Đi qua proxy hệ thống' trong Setting > API nếu MES "
                   "là máy chủ nội bộ.") % code)
    if len(t) > 200:
        t = t[:200] + "…"
    if code:
        return "HTTP %s: %s" % (code, t)
    return t


def _make_session(use_proxy, proxy):
    """Tạo Session + cấu hình proxy (mặc định bỏ qua proxy hệ thống)."""
    session = requests.Session()
    if not use_proxy:
        session.trust_env = False        # bỏ qua HTTP_PROXY/HTTPS_PROXY của hệ thống
        proxies = {"http": None, "https": None}
    elif proxy:
        proxies = {"http": proxy, "https": proxy}
    else:
        proxies = None                   # để requests tự lấy proxy hệ thống
    return session, proxies


# ---------------------------------------------------------------------- #
#  Kiểm tra SN bằng GET (trước khi cho chạy)                              #
# ---------------------------------------------------------------------- #
def check_sn(sn, prefix, suffix="", ok_contains="0", timeout=5.0,
             verify_ssl=True, use_proxy=False, proxy="", logger=None):
    """GET tới prefix+SN+suffix; SN hợp lệ nếu body CHỨA 'ok_contains'.

    Trả về (ok: bool, message: str). ok=False khi: GET lỗi mạng, HTTP != 2xx,
    hoặc body KHÔNG chứa chuỗi mong đợi -> bên gọi sẽ CHẶN, chờ quét mã khác.
    """
    if requests is None:
        return False, tr("Chưa cài thư viện 'requests'")
    url = "%s%s%s" % (prefix or "", sn, suffix or "")
    try:
        session, proxies = _make_session(use_proxy, proxy)
        resp = session.get(url, timeout=timeout, verify=verify_ssl,
                           proxies=proxies)
        body = (resp.text or "").strip()
        if logger:
            logger("GET check SN -> HTTP %d" % resp.status_code)
        if not (200 <= resp.status_code < 300):
            return False, tr("MES từ chối kiểm tra SN (HTTP %d): %s") \
                % (resp.status_code, short_error(resp.status_code, body))
        if ok_contains and ok_contains not in body:
            # body thường chứa lý do (vd 'da test', 'trung SN'...) -> hiện ra
            return False, (body[:200] if body else tr("SN không hợp lệ (MES không trả mã cho phép)"))
        return True, tr("SN hợp lệ")
    except Exception as ex:               # noqa: BLE001
        return False, tr("Lỗi GET kiểm tra SN: %s") % ex


# ---------------------------------------------------------------------- #
#  Gửi POST (có retry khi lỗi mạng)                                       #
# ---------------------------------------------------------------------- #
def post_payload(url, payload, timeout=5.0, retries=3, verify_ssl=True,
                 use_proxy=False, proxy="", ok_contains="", logger=None):
    """Trả về (ok: bool, status_code, text). Retry kiểu lùi dần 2,4,8s.

    use_proxy=False: bỏ qua proxy hệ thống (trust_env=False) — phù hợp MES nội bộ.
    use_proxy=True : dùng 'proxy' nếu có nhập, ngược lại dùng proxy hệ thống.
    ok_contains    : nếu có, POST chỉ THÀNH CÔNG khi body CHỨA chuỗi này
                     (kể cả HTTP 200). Để trống -> chỉ dựa HTTP 2xx.
    """
    if requests is None:
        msg = "Chua cai thu vien 'requests'"
        if logger:
            logger(msg)
        return False, None, msg

    session, proxies = _make_session(use_proxy, proxy)

    last_err = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            resp = session.post(url, json=payload, timeout=timeout,
                                verify=verify_ssl, proxies=proxies)
            http_ok = 200 <= resp.status_code < 300
            body = resp.text or ""
            ok = http_ok and (not ok_contains or ok_contains in body)
            if logger:
                logger("POST #%d -> HTTP %d" % (attempt, resp.status_code))
            if ok:
                return True, resp.status_code, body
            # HTTP 2xx nhưng body không chứa chuỗi mong đợi -> MES báo lỗi
            if http_ok and ok_contains and ok_contains not in body:
                return False, resp.status_code, body
            # HTTP lỗi (4xx/5xx) -> không retry vô ích với 4xx
            if resp.status_code < 500:
                return False, resp.status_code, body
            last_err = "HTTP %d" % resp.status_code
        except Exception as ex:          # noqa: BLE001  (lỗi mạng -> retry)
            last_err = str(ex)
            if logger:
                logger("POST #%d loi: %s" % (attempt, last_err))
        if attempt < retries:
            time.sleep(min(2 ** attempt, 8))
    return False, None, str(last_err)
