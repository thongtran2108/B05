# -*- coding: utf-8 -*-
"""Kiểm thử: GET kiểm tra SN + POST với tiêu chí body chứa chuỗi.

Dùng monkeypatch một 'requests' giả để không cần server thật.

Chạy:  python -m tests.test_api_check
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mes_uploader import mes_api


class _Resp:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


class _FakeSession:
    """Giả requests.Session: trả kết quả theo bảng route đã nạp."""
    routes = {}        # url -> (status_code, text)

    def __init__(self):
        self.trust_env = True

    def get(self, url, **kw):
        sc, txt = _FakeSession.routes.get(("GET", url), (404, "not found"))
        return _Resp(sc, txt)

    def post(self, url, **kw):
        sc, txt = _FakeSession.routes.get(("POST", url), (404, "not found"))
        return _Resp(sc, txt)


class _FakeRequests:
    Session = _FakeSession


def main():
    mes_api.requests = _FakeRequests   # monkeypatch

    # ---- GET kiểm tra SN (so khớp BẰNG ĐÚNG, giống main.py: req.text == '0') ----
    pre = "http://mes/check?sn="
    _FakeSession.routes = {
        ("GET", pre + "GOOD"): (200, "0"),            # body == '0' -> hợp lệ
        ("GET", pre + "USED"): (200, "đã test rồi"),  # body != '0'  -> chặn
        ("GET", pre + "DUP"): (200, "100"),           # CHỨA '0' nhưng != '0' -> chặn
        ("GET", pre + "ERR"): (500, "server error"),  # HTTP lỗi      -> chặn
    }
    ok, msg = mes_api.check_sn("GOOD", pre, ok_value="0")
    print("GET GOOD ->", ok, "|", msg); assert ok is True

    ok, msg = mes_api.check_sn("USED", pre, ok_value="0")
    print("GET USED ->", ok, "|", msg); assert ok is False and "test" in msg

    # body '100' CHỨA '0' nhưng KHÁC '0' -> phải chặn (lỗi cũ: 'chứa' sẽ nhận nhầm)
    ok, msg = mes_api.check_sn("DUP", pre, ok_value="0")
    print("GET DUP  ->", ok, "|", msg); assert ok is False and "100" in msg

    ok, msg = mes_api.check_sn("ERR", pre, ok_value="0")
    print("GET ERR  ->", ok, "|", msg[:40]); assert ok is False

    # ---- POST với ok_contains ----
    url = "http://mes/upload"
    _FakeSession.routes = {("POST", url): (200, '{"code":"200","msg":"ok"}')}
    ok, code, text = mes_api.post_payload(url, {"sn": "x"}, retries=1,
                                          ok_contains="200")
    print("POST body chứa 200 ->", ok); assert ok is True

    # HTTP 200 nhưng body KHÔNG chứa chuỗi -> thất bại (MES báo lỗi logic)
    _FakeSession.routes = {("POST", url): (200, '{"code":"500","msg":"trung SN"}')}
    ok, code, text = mes_api.post_payload(url, {"sn": "x"}, retries=1,
                                          ok_contains="200")
    print("POST body thiếu 200 ->", ok, "| body:", text); assert ok is False

    # ok_contains rỗng -> chỉ cần HTTP 2xx
    _FakeSession.routes = {("POST", url): (200, "anything")}
    ok, code, text = mes_api.post_payload(url, {"sn": "x"}, retries=1,
                                          ok_contains="")
    print("POST ok_contains rỗng + HTTP200 ->", ok); assert ok is True

    print("\nTEST API-CHECK PASS ✔")


if __name__ == "__main__":
    main()
