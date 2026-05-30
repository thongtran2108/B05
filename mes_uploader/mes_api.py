# -*- coding: utf-8 -*-
"""Dựng JSON và POST nội dung lên hệ thống MES.

Theo yêu cầu:
  - 1 SN gọi API 1 lần, GỘP dữ liệu của tất cả các đầu.
  - Trường "data" chỉ chứa các giá trị đo Data01..N (data_format mặc định
    = "values_only"). Vẫn hỗ trợ thêm "full_row" / "structured" để chỉnh
    nhanh trong Setting nếu MES cần định dạng khác.
  - JSON: {"sn": ..., "result": "OK"/"NG", "data": ...}
"""

import time

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
def build_payload(sn, readings, data_format="values_only"):
    """readings: list dict trả về từ data_reader.read_latest_measurement,
    theo đúng thứ tự các lần chạy (đầu 1, đầu 2, ...).

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
        "result": overall_result(readings),
        "data": data,
    }


# ---------------------------------------------------------------------- #
#  Gửi POST (có retry khi lỗi mạng)                                       #
# ---------------------------------------------------------------------- #
def post_payload(url, payload, timeout=5.0, retries=3, verify_ssl=True,
                 logger=None):
    """Trả về (ok: bool, status_code, text). Retry kiểu lùi dần 2,4,8s."""
    if requests is None:
        msg = "Chua cai thu vien 'requests'"
        if logger:
            logger(msg)
        return False, None, msg

    last_err = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            resp = requests.post(url, json=payload, timeout=timeout,
                                 verify=verify_ssl)
            ok = 200 <= resp.status_code < 300
            if logger:
                logger("POST #%d -> HTTP %d" % (attempt, resp.status_code))
            if ok:
                return True, resp.status_code, resp.text
            # HTTP lỗi (4xx/5xx) -> không retry vô ích với 4xx
            if resp.status_code < 500:
                return False, resp.status_code, resp.text
            last_err = "HTTP %d" % resp.status_code
        except Exception as ex:          # noqa: BLE001  (lỗi mạng -> retry)
            last_err = str(ex)
            if logger:
                logger("POST #%d loi: %s" % (attempt, last_err))
        if attempt < retries:
            time.sleep(min(2 ** attempt, 8))
    return False, None, str(last_err)
